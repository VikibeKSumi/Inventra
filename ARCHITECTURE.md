# Inventra - Architecture

## Contents

- [Layers](#layers)
- [Module map](#module-map)
- [Orchestrator](#orchestrator)
- [Agents](#agents)
- [HITL and deterministic nodes](#hitl-and-deterministic-nodes)
- [State contract](#state-contract)
- [Workflow paths](#workflow-paths)
- [Data model](#data-model)
- [Adding a tool or an agent](#adding-a-tool-or-an-agent)

## Layers

Each layer hides its own mess, so the layer above it reads clean. A layer may call the one below it and nothing above it.

**Schemas** (`schemas/`) - the contracts. Inputs reject any field not declared; outputs are frozen. Every capability returns the same `ToolResult` envelope - success, a result code from a fixed set, a typed payload, a message, and the evidence it read. Nothing here knows about databases, prompts or graphs.

**Repository** (`capabilities/repository/`) - the only place SQL exists. Takes plain arguments, returns plain rows, makes no decisions. The clock lives here too, so time is a dependency rather than a call to `datetime.now()`.

**Capabilities** (`capabilities/`) - all the real logic: freshness, cover, sizing, feasibility, the write. Each method takes a typed input model and returns a `ToolResult`. Thresholds come from config, never from literals in the code. This layer is callable and testable without any LLM, graph or tool wrapper.

**Tools** (`tools/`) - thin wrappers that expose some capabilities to the model, plus the per-agent allowlist. A wrapper validates the model's arguments, calls the capability and serialises the result. It holds no logic of its own. Capabilities that must never be model-invoked - the purchase write - simply have no wrapper here.

**Prompts** (`prompts/`) - role and judgement only. What an agent is for, how to choose, how to explain. Never facts, never thresholds, never guarantees - those live in structure, where they can be enforced.

**Nodes** (`nodes/`) - state in, state update out. LLM nodes and agents call tools and write explanations; HITL nodes pause for a person; deterministic nodes do plain work. No node decides where the case goes next.

**Workflow** (`workflow/`) - routers and wiring. Routers read one status field and return a node name; the graph declares nodes, edges and the checkpointer. Deterministic, with no LLM anywhere.

**State** (`state/`) - the shared whiteboard every node reads and writes, with reducers deciding what accumulates rather than replaces.

**Config** (`config/`) - one frozen object holding every threshold and path, injected from the outside so tests and notebooks can supply their own.

The rule that keeps this honest: facts, maths and verdicts flow up from the bottom; interpretation and explanation happen at the top. Nothing at the top invents a value the bottom didn't produce.

## Module map

| Path | Holds | Never holds |
|---|---|---|
| `schemas/capability_schemas.py` | tool/capability input and output models, `ToolResult`, `EvidenceRef` | logic, SQL |
| `schemas/llm_schemas.py` | structured outputs the model must return (`OrchestratorOutput`, `OfferSelection`) | anything a tool returns |
| `capabilities/capabilities.py` | `CapabilityService` - all business logic and the single write | SQL, prompts, graph awareness |
| `capabilities/repository/sqlite_repository.py` | every SQL statement | decisions, thresholds |
| `capabilities/repository/clock.py` | the injected `Clock` | anything else |
| `tools/build_tools.py` | `@tool` wrappers + `AGENT_TOOL_ACCESS` allowlist | logic |
| `prompts/prompts.py` | the system prompts - role and judgement | facts, thresholds |
| `nodes/llm/orchestrator.py` | the routing decision node | tools |
| `nodes/agents/` | the two agents: tool loop, view, status gate walk | routing, arithmetic |
| `nodes/hitl/` | `clarify_hitl`, `approve_hitl` - the two `interrupt()` pauses | side effects before the interrupt |
| `nodes/deterministic/` | `out_of_scope`, `create_purchase_request` | LLM calls |
| `workflow/router.py` | status → node lookups, one per branching node | state mutation |
| `workflow/workflow.py` | `InventraGraph` - nodes, edges, checkpointer, compile | business logic |
| `state/state.py` | `InventraState` and its reducers | defaults, behaviour |
| `config/config.py` | every threshold, path and cap, frozen | environment reading |
| `data/` | `schema.sql`, the seeded `inventra.db`, `policy.md` | code |
| `tests/` | branch-level tests of the capability layer | |
| `exploratory_testing/` | notebooks for running the real thing and eyeballing output | committed assertions |
| `run.py` | the composition root - builds llm, service, config, clock and runs the graph | logic of its own |

## Orchestrator

The front door. It reads the conversation and decides who should handle it - nothing else. It has no tools, so it cannot look anything up, and it never answers the question itself.

Its output is a fixed structure rather than prose: a destination, plus whatever it could extract from what the user actually said - the SKU, the warehouse, a target cover in days, a preference for cheapest or fastest. It is told not to invent any of them. A missing SKU or warehouse is a reason to ask, not to guess.

Four destinations:

- **inventory agent** - anything about checking stock or risk, including the first step of "check it and restock if needed".
- **replenishment agent** - an explicit request to reorder, or to reshape an existing proposal.
- **clarify** - a required detail is missing or the ask is unclear.
- **out of scope** - the request is not a stock check or a restock at all, like creating a product or editing a vendor. It judges the *action* being asked for, not whether the SKU happens to exist - that is a fact for the tools to establish later.

It reads the whole message thread every time, not just the latest message. So when a person answers a clarifying question, the orchestrator sees the original request and the answer together and routes normally, rather than asking again.

Because its decision is a value from a fixed set, the router that acts on it is plain code with no interpretation of its own.

## Agents

Each agent has one narrow job and only the tools that job needs. Neither decides where the case goes next; they report, and code routes.

### Inventory agent

Answers one question: is this SKU at risk in this warehouse?

It confirms the product exists and is active, then asks the risk tool for days of cover, the projected stockout date and the verdict. It writes the explanation in plain language, citing the numbers the tools returned.

The verdict itself is not the model's to make. Code reads the tool results and sets the status: `at_risk`, `healthy`, `blocked` when the product is missing, inactive or the snapshot is stale, and `needs_information` when there is too little sales history to judge. The model can describe the situation; it cannot decide it.

Tools: `get_product`, `get_stock_position`, `get_sales_velocity`, `calculate_stock_risk`.

### Replenishment agent

Turns an at-risk item into a proposal a person can approve.

It reads the company purchasing policy, then asks for the buying options. Those come back already sized to restore the target cover, priced, and marked eligible or not against vendor reliability, delivery time and the remaining budget - so no arithmetic or feasibility call is left to the model.

Its one real judgement is choosing between the options that are already eligible, guided by whether the request favoured cost, speed or a balance. That choice comes back as a structured offer id, and code checks the id is genuinely in the eligible set before accepting it. The numbers written into the proposal are copied from the tool result, never retyped by the model.

Status is again set in code: `awaiting_approval` when a valid option was chosen, `blocked` when nothing was feasible, the budget could not cover it, or the risk check itself failed.

Tools: `get_policy_guidance`, `build_vendor_options`, and for explaining a failure, `list_vendor_offers`, `get_vendor_performance`, `get_budget_position`.

## HITL and deterministic nodes

### Clarify

Runs when the orchestrator says a required detail is missing. It pauses with the question, and the answer comes back on resume. Both the question and the answer are written into the conversation, so when the orchestrator runs again it sees the original request and the reply together and routes normally instead of asking twice.

### Approve

The gate in front of the money. It pauses with the full proposal - the prose explanation plus the structured numbers a person needs to judge it: vendor, offer, quantity, unit price, total cost, expected arrival.

The reply must carry a decision and a named approver; neither is optional, and an unrecognised decision is rejected rather than routed. Approve stamps the approval time from the injected clock. Revise sends the case back for a fresh proposal and increments a counter, so revisions cannot cycle forever.

Both HITL nodes follow the same rule: on resume, a node re-runs from its first line, not from the pause. So nothing with a side effect may sit above the `interrupt()` call - only reads.

### Out of scope

Terminal and trivial. It turns the orchestrator's decline into a reply the user actually sees and records why the case ended. It exists as a node rather than an edge to END because someone has to deliver the message and set the outcome.

### Create purchase request

The system's only write, and the only node that changes anything outside the process.

It takes the approved figures - copied from the tool result, never retyped by a model - and inserts one purchase request. The idempotency key is derived from the approval itself, and the table enforces it as unique. Before inserting it looks the key up; if the row already exists it returns that order instead of creating another. If two runs race, the unique constraint catches the loser and it returns the existing row.

Nothing here is a tool. There is no wrapper, so no agent can reach it. It is called directly by the node, only after approval, and every failure returns a stated reason rather than raising - a case that cannot be written ends cleanly rather than crashing the graph.

## State contract

State is the shared whiteboard. Every node receives it, returns only the fields it changed, and LangGraph merges the update. Two fields accumulate rather than replace: `messages` and `evidence`. Everything else is overwritten by whoever writes it last.

| Fields | Written by | Read by |
|---|---|---|
| `messages` | the user, clarify, out of scope | orchestrator (the whole thread, every time) |
| `next_destination`, `instruction`, `sku`, `warehouse_id`, `target_cover_days`, `strategy_hint`, `clarification_question`, `decline_reason` | orchestrator | its router, both agents, clarify, out of scope |
| `inventory_status`, `inventory_explanation` | inventory agent | its router |
| `replenishment_status`, `replenishment_proposal`, `vendor_id`, `offer_id`, `quantity`, `unit_price`, `total_cost`, `expected_arrival` | replenishment agent | its router, approve, the write |
| `decision`, `approver`, `comment`, `proposal_revision`, `approved_at`, `revision_count` | approve | its router, the write |
| `purchase_request_id`, `status`, `terminal_reason`, `error_code` | out of scope, the write | the caller |
| `evidence` | every node that reads data | the audit trail |

Three rules hold it together.

**Routing reads a status field, never prose.** Each branching node writes one status - `next_destination`, `inventory_status`, `replenishment_status`, `decision` - and its router reads exactly that.

**Structured fields cross node boundaries, not paragraphs.** The write takes `quantity` and `total_cost` as values the tools produced; nothing downstream parses a number out of an explanation.

**The state schema is total=False.** A field exists only once something writes it, so nodes read with `.get()` and an absent field means "this never happened" rather than "this is empty".

## Workflow paths

Every route a case can take, end to end.

1. **Out of scope** - the request isn't a stock check or a restock, so the orchestrator declines, says what it can help with, and the case ends without touching any data.

2. **Clarification** - a required detail is missing. The graph pauses, asks, and resumes on the same thread with the answer recorded in the conversation. The orchestrator then re-reads the whole thread and routes normally, so the question is never repeated.

3. **Healthy** - the inventory agent finds enough cover. The case ends there; no vendor work, no proposal.

4. **Blocked at assessment** - the product is missing or inactive, the snapshot is stale, or there is too little sales history to judge. The case ends with the reason stated, rather than proceeding on bad evidence.

5. **At risk, but nothing feasible** - the item genuinely needs stock, but no vendor clears the reliability bar, delivers before the stockout, or fits the remaining budget. The case ends explaining which blocker applied to each option.

6. **At risk, proposal approved** - a feasible option is chosen and presented. A named person approves, and exactly one purchase request is written. Re-running it returns the same order rather than placing a second.

Two variations on the last one: the approver can **reject**, which ends the case, or ask for a **revision**, which sends it back for a fresh proposal. Revisions are capped, so the loop always terminates.

A case reaches the write only by passing through every gate before it - evidence checked, options proven feasible, and a person's explicit approval.

## Data model

Eight tables in SQLite. The system reads seven of them and writes exactly one.

| Table | What it holds | Used for |
|---|---|---|
| `products` | SKU, name, category, active flag | confirming an item exists and isn't discontinued |
| `inventory_snapshots` | on hand, reserved, confirmed inbound, `captured_at` | available stock, and the freshness check |
| `sales_daily` | units sold per day per SKU per warehouse | sales pace, and whether there is enough history to trust it |
| `vendors` | on-time rate, fill rate, quality score, active flag | the reliability bar |
| `vendor_offers` | price, MOQ, lead time, `valid_until` | who can supply it, on what terms |
| `monthly_budgets` | budget, spent, committed | what is left to spend this month |
| `purchase_requests` | the order, its status, approver and idempotency key | **the only table written** |
| `audit_events` | case, trace, actor, event type, payload | reserved for the audit trail |

Two things shape how the code treats this data.

**It belongs to other systems.** Stock and sales are produced by warehouse and sales operations, not by Inventra. So a snapshot carries its own capture time, and anything older than the freshness limit blocks the case rather than being used. The system never corrects or backfills data it doesn't own.

**SQLite has no timezone type.** Timestamps are stored naive in UTC and parsed back as timezone-aware at the repository boundary, so every comparison happens against the injected clock rather than whatever the machine's local time happens to be.

`purchase_requests.idempotency_key` carries a unique constraint. That constraint, not application logic, is what ultimately guarantees one approval can only ever produce one order.

## Adding a tool or an agent

### A new tool

Build it output-first, so each step has something concrete to satisfy:

1. **Payload schema** - what the caller gets back, as a frozen output model. Decide this before anything else; it forces you to say what the tool is actually for.
2. **Input schema** - what it needs, with `extra="forbid"` so nothing undeclared slips through.
3. **Repository method** - the SQL, returning plain rows.
4. **Capability method** - the logic. Takes the input model, returns a `ToolResult` with a result code from the fixed set and an `EvidenceRef` for every record it read. Thresholds come from config.
5. **Tool wrapper** - a thin `@tool` that validates the model's arguments, calls the capability and serialises the result. No logic.
6. **Allowlist** - add the tool name to the agents that should have it. The startup check fails loudly if the name doesn't match a real tool.
7. **Tests** - one per branch, including the failure paths. Use a fake repository for cases the seed data can't reach.

If the capability must never be model-invoked, stop after step 4 and call it directly from a node - that is how the purchase write stays out of reach.

### A new agent

1. **Prompt** - role, how to use its tools, how to decide, how to explain. No facts, no thresholds.
2. **Allowlist entry** - only the tools that role needs.
3. **Node class** - injected llm, service and config; a view of the structured fields it shouldn't have to parse from prose; the tool loop with an iteration cap; one try/except that converts any failure into a blocked status.
4. **Status in code** - a gate walk over the tool results. The model explains; it never sets the verdict.
5. **Router** - a flat map from status to node name, raising on anything unrecognised.
6. **Wire it** - register the node and its conditional edges in the graph.

### A new route

Adding a destination means touching three places, and all three must agree on the node name: the schema or status that can produce it, the router's map, and `add_node` in the graph. A mismatch surfaces at compile time, which is the point.


---

[the problem](DESIGN.md#the-problem)
