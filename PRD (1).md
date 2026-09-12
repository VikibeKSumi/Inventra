# Inventra Replenishment Advisor — Product Requirements Document

Version date: September 12, 2026
Status: Phase 1 in delivery

---

## 1. Customer Problem

A procurement manager is responsible for keeping stock available across warehouses without breaching a monthly purchase budget. Today that decision is assembled by hand.

To decide whether a single SKU needs replenishment, the manager must pull the latest inventory snapshot, pull thirty days of sales history, work out a daily sales rate, convert that into days of cover, project a stockout date, collect the live vendor quotes for that SKU, discard the expired ones, check each vendor's delivery reliability, size an order against each vendor's minimum order quantity, price it, check it against the remaining budget, and confirm the delivery would actually arrive before stock runs out.

This produces four recurring failures:

- **Late detection.** Risk is noticed when stock is nearly gone, at which point only the fastest and most expensive vendor can still help.
- **Decisions on stale evidence.** An inventory snapshot from four days ago looks identical to one from four hours ago in a spreadsheet.
- **Inconsistent trade-offs.** Two managers facing the same SKU choose different vendors, and neither decision records why.
- **No traceability.** When a purchase is questioned a week later, nobody can reconstruct which numbers it was based on.

The cost lands on both sides. Under-ordering loses sales; over-ordering locks capital and breaches budget. Both are avoidable with evidence that is already sitting in the system.

Inventra Replenishment Advisor removes the manual assembly. It gathers the evidence, computes the risk, evaluates every live vendor offer against cost, arrival and budget, and presents a single traceable proposal for a named human to approve, revise or reject.

---

## 2. System Boundary

### Existing system: Inventra

Inventra is the operational system of record. It owns:

- the product catalogue
- inventory snapshots per SKU and warehouse
- daily sales history
- the vendor master and vendor performance metrics
- vendor offers, including price, minimum order quantity, lead time and expiry
- monthly purchase budgets per warehouse
- purchase requests

Inventra remains the source of truth for all of the above. Our system reads it and, on approval, writes exactly one kind of record into it: a purchase request.

### Our system: Inventra Replenishment Advisor

The Advisor owns replenishment decision support and nothing else. It owns:

- risk assessment for a SKU and warehouse
- evidence gathering and evidence freshness judgement
- vendor offer evaluation and ranking
- proposal drafting, versioning and revision
- the human approval loop
- revalidation before execution
- the case audit trail

The Advisor reaches Inventra only through a typed tool layer. No agent, prompt or LLM response ever issues SQL, touches a table directly, or produces a number that was not computed by a tool. The Advisor does not rebuild inventory management, does not rebuild the vendor master, and does not become a second source of truth for any fact it displays.

The one write path is `create_purchase_request`, and it fires only after a named human has approved a specific proposal version and the proposal has been revalidated against current data.

---

## 3. User Workflows

All workflows run against warehouse `DEL-01` in the starter dataset.

### Workflow 1 — Assess a single SKU

1. The manager names a SKU and warehouse.
2. Evidence is gathered: product, latest snapshot, sales velocity.
3. Snapshot freshness and sales sufficiency are checked.
4. Stock risk is computed against the risk threshold.
5. If coverage is healthy, recovery closes with `NO_ACTION`.

```
Manager: Is AC-001 at risk in DEL-01?

Advisor: No action needed. AC-001 has 40 units available against a
         30-day average of 3.0 units/day, which is 13.3 days of cover.
         Projected stockout is 12 Sep, well past the 10-day risk
         threshold.
         Evidence: INV-AC001-1 (snapshot, 1.5h old), 30 days of sales.
```

### Workflow 2 — Replenishment proposal and approval

1. Risk is confirmed and a shortfall quantity is computed.
2. Live vendor offers are retrieved; expired offers and vendors below the reliability bar are excluded with a stated reason.
3. Each remaining offer is sized, priced, and checked against arrival date and remaining budget.
4. One offer is proposed, with the trade-off against the alternatives stated explicitly.
5. The proposal is versioned and held for a named approver.
6. On approval the proposal is revalidated, then a purchase request is created.

```
Manager: AC-003 is looking thin, can you sort it out?

Advisor: AC-003 is at risk. 15 units available, 2.0 units/day,
         7.5 days of cover, projected stockout 6 Sep.

         Recommended: FastShip Inc. (V-FAST), 49 units at ₹300,
         total ₹14,700, arriving 1 Sep.

         Trade-off: BudgetVendor Ltd. would cost ₹10,620, saving
         ₹4,080, but their 7-day lead time lands the delivery on
         6 Sep, the same day stock runs out. That leaves no margin,
         so it is excluded as infeasible rather than offered as a
         cheaper option.

         Remaining August budget after this order: ₹300.
         Evidence: INV-AC003-1, OFFER-003-2, BUDGET-DEL01-2026-08.
         Proposal PROP-CASE-AC003-DEL01-REV1 is awaiting approval.

Manager: Approved.

Advisor: I need a named approver on the record before I can proceed.

Manager: Approved by Asha Mehta.

Advisor: Revalidated and executed. Purchase request PR-C5383CF2311F
         created, status PENDING, 49 units from V-FAST.
         Committed budget updated.
```

### Workflow 3 — Revision after human feedback

1. The approver rejects or requests a change to a specific proposal version.
2. The instruction is interpreted into changed parameters.
3. The pipeline reruns and produces a new version. The earlier version is never edited.

```
Manager: ₹14,700 is too much. Find something cheaper.

Advisor: The only cheaper offer for AC-003 is BudgetVendor at
         ₹10,620, and it arrives the day stock runs out, so it
         cannot be recommended as-is.

         Two options that do work:
         - Reduce the target cover from 30 days to 15 days. That cuts
           the FastShip order to 19 units at ₹5,700 and still arrives
           1 Sep.
         - Accept BudgetVendor as an explicit exception, on record
           that there is no delivery margin.

Manager: Do the 15-day one.

Advisor: PROP-CASE-AC003-DEL01-REV2 created. 19 units from V-FAST,
         ₹5,700, arriving 1 Sep, cover restored to 15 days.
         REV1 remains on record as superseded.
```

### Workflow 4 — Blocked and incomplete cases

The Advisor stops rather than guessing. Each stop states what blocked it and what would unblock it.

```
Manager: Check AC-002.

Advisor: Blocked. The latest snapshot for AC-002 (INV-AC002-1) was
         captured 79 hours ago, past the 48-hour freshness limit.
         I will not size an order against stock data this old.
         A fresh snapshot for AC-002 in DEL-01 unblocks this case.
```

```
Manager: What about AC-005?

Advisor: I need more information. AC-005 has only 14 days of sales
         history against a 21-day minimum, so the daily rate is not
         reliable enough to size an order. Current cover looks
         comfortable, but I am not treating that as a finding.
         Either wait for more history or supply a manual demand
         estimate.
```

```
Manager: AC-004, we cannot run out of those.

Advisor: Blocked on budget. AC-004 is critical, 4.0 days of cover,
         projected stockout 3 Sep. Restoring 30 days of cover needs
         87 units, ₹39,150 from Standard Supplier or ₹42,000 from
         FastShip. Remaining August budget for DEL-01 is ₹15,000.

         This needs either a budget exception, a smaller partial
         order, or deferral into September. I am not sizing down
         silently, because a partial order changes what you are
         approving.
```

```
Manager: And AC-006?

Advisor: Blocked. No valid vendor options. Shady Vendor LLC and
         SlowShip Co. are both below the reliability bar, and the
         FastShip offer for AC-006 expired on 29 Aug. A current
         offer from a qualifying vendor unblocks this case.
```

### Workflow 5 — Approval invalidated at execution

1. An approved proposal is revalidated immediately before the write.
2. If freshness, offer validity or budget position has moved materially, the approval is voided and the case returns for review.

```
Advisor: Approval for PROP-CASE-AC004-DEL01-REV1 has been
         invalidated. Remaining budget dropped from ₹15,000 to
         ₹8,200 between approval and execution, and the order no
         longer fits. No purchase request was created. The case is
         back in review.
```

---

## 4. Required Capabilities

### 4.1 Workflow needs to tools

| Workflow need | Required capability | Tool | Phase |
|---|---|---|---|
| Confirm the SKU exists and is active | Product lookup | `get_product` | 1 |
| Know current stock and whether it can be trusted | Snapshot retrieval with freshness | `get_inventory_snapshot` | 1 |
| Know how fast the SKU sells and whether that is reliable | Velocity with sufficiency | `get_sales_velocity` | 1 |
| Know if the SKU is actually at risk | Risk computation | `compute_stock_risk` | 1 |
| Know what can be bought and from whom | Live offer retrieval | `get_vendor_offers` | 1 |
| Know what can be afforded | Budget position | `get_budget_position` | 1 |
| Size an order correctly | Quantity computation | `compute_reorder_quantity` | 1 |
| Know which offers are actually feasible | Offer evaluation | `evaluate_offers` | 1 |
| Order feasible offers by intent | Strategy ranking | `rank_offers` | 1 |
| Hold a versioned, traceable recommendation | Proposal creation | `create_proposal` | 2 |
| Record a named human decision | Decision capture | `record_decision` | 2 |
| Confirm nothing moved before writing | Revalidation | `revalidate_proposal` | 2 |
| Create the purchase order safely | Idempotent write | `create_purchase_request` | 2 |
| Reconstruct any case afterwards | Audit trail | `log_audit_event` | 2 |
| Resume an interrupted case | State retrieval | `get_case_state` | 2 |
| Scan a whole warehouse for risk | Bulk risk scan | `scan_warehouse_risk` | 4 |

Read tools, computation tools and action tools stay in separate modules. Every tool returns a structured result with an explicit status field and never raises into the agent. Every evidence tool returns the identifier of the record it read.

### 4.2 State

The Advisor is a case machine, not a chat log. One case covers one SKU, one warehouse and one replenishment question.

```
CaseState
  case_id                str            CASE-<SKU>-<WAREHOUSE>
  trace_id               str            one per case, on every audit event
  as_of                  datetime       injected clock, never datetime.now()

  request
    sku                  str
    warehouse_id         str
    target_cover_days    int            defaults from config, overridable
    strategy_hint        str | None     cheapest | fastest | balanced

  evidence                               populated only by tools
    product              ProductRef | None
    snapshot             SnapshotRef | None
    velocity             VelocityRef | None
    offers               list[OfferRef]
    budget               BudgetRef | None

  analysis
    risk                 RiskResult | None
    evaluated_offers     list[EvaluatedOffer]
    ranked               dict[str, list[str]]

  proposal
    current_version      int
    history              list[ProposalRef]

  decision
    status               NO_ACTION | BLOCKED | NEEDS_INFORMATION
                         | AWAITING_APPROVAL | APPROVED | EXECUTED | CLOSED
    blocked_reasons      list[str]
    approver             str | None
    feedback             str | None

  messages               list                conversation turns
```

Three rules govern this state:

- Tools write to `evidence` and `analysis`. The LLM writes only to `messages`, `request.strategy_hint` and `decision.feedback`.
- `proposal.history` is append-only. A revision creates `REV n+1`; no version is ever edited.
- State is checkpointed after every node so a case can survive the gap between proposal and human approval, which may be hours.

### 4.3 LangGraph agent design

**Graph shape.** A single graph with deterministic routing. Conditional edges read status flags set by tools, never free text produced by a model.

```
                        ┌──────────┐
                        │  intake  │  LLM: parse request into typed args
                        └────┬─────┘
                             ▼
                    ┌─────────────────┐
                    │ gather_evidence │  5 tools, parallel fan-out
                    └────────┬────────┘
                             ▼
                    ┌─────────────────┐
                    │  gate_evidence  │  missing / stale / insufficient
                    └────────┬────────┘
                   ┌─────────┼─────────┐
                   ▼         ▼         ▼
              [BLOCKED] [NEEDS_INFO]   │  pass
                                       ▼
                              ┌────────────────┐
                              │  assess_risk   │
                              └───────┬────────┘
                            ┌─────────┴────────┐
                            ▼                  ▼
                       [NO_ACTION]     ┌────────────────┐
                                       │ evaluate_offers│
                                       └───────┬────────┘
                                     ┌─────────┴────────┐
                                     ▼                  ▼
                               [BLOCKED]        ┌────────────────┐
                            no feasible offer   │ draft_proposal │  LLM
                                                └───────┬────────┘
                                                        ▼
                                                ┌────────────────┐
                                                │  human_review  │  interrupt()
                                                └───────┬────────┘
                                     ┌──────────────────┼──────────────┐
                                     ▼                  ▼              ▼
                              ┌────────────┐      [REJECTED]    ┌────────────┐
                              │ revalidate │                    │   revise   │  LLM
                              └─────┬──────┘                    └─────┬──────┘
                          ┌─────────┴────────┐                        │
                          ▼                  ▼                        │
                     ┌─────────┐      [INVALIDATED] ──────────────────┘
                     │ execute │       back to review
                     └────┬────┘
                          ▼
                       [CLOSED]
```

**Nodes and ownership.**

| Node | Calls the LLM | Responsibility |
|---|---|---|
| `intake` | Yes | Free text to typed request arguments. Resolves SKU through `get_product`, never by guessing. |
| `gather_evidence` | No | Fans out the five evidence tools, collects refs and statuses. |
| `gate_evidence` | No | Applies the gate order below and sets terminal status if any gate fails. |
| `assess_risk` | No | `compute_stock_risk`. Routes to `NO_ACTION` if healthy. |
| `evaluate_offers` | No | Sizes, prices and checks every offer. Routes to `BLOCKED` if none are feasible. |
| `draft_proposal` | Yes | Picks a strategy from the feasible set, writes the human-readable rationale, cites evidence IDs. |
| `human_review` | No | `interrupt()`. Holds until a named approver responds. |
| `revise` | Yes | Turns feedback into changed request parameters and re-enters the pipeline. |
| `revalidate` | No | Re-runs freshness, offer validity and budget checks against current data. |
| `execute` | No | Idempotent purchase request write plus budget commitment, in one transaction. |

**Gate order in `gate_evidence`.** Fixed and non-negotiable, because a later gate's result is meaningless if an earlier one fails:

1. Evidence present (missing product, snapshot, offers or budget row → `BLOCKED`)
2. Snapshot freshness (→ `BLOCKED`)
3. Sales sufficiency (→ `NEEDS_INFORMATION`)
4. Risk assessment (healthy → `NO_ACTION`)
5. Vendor validity and reliability (none left → `BLOCKED`)
6. Budget feasibility (→ `BLOCKED`)

**Durability.** A SQLite checkpointer persists state per `case_id` as thread ID. The interrupt at `human_review` is the reason this is required, not optional: approval arrives in a separate session from proposal.

**Untrusted input.** `vendors.notes` is free text supplied by a third party. It is passed to the model as quoted data with an explicit non-instruction frame, and the model has no tool that could act on an instruction found there.

---

## 5. Deterministic vs Agentic Behaviour

| Behaviour | Ownership |
|---|---|
| Read any product, snapshot, sales, vendor, offer or budget record | Deterministic capability |
| Decide whether a snapshot is fresh enough | Deterministic |
| Compute sales velocity and judge whether history is sufficient | Deterministic |
| Compute available stock, days of cover and projected stockout date | Deterministic |
| Decide whether a SKU is at risk | Deterministic |
| Exclude expired offers and vendors below the reliability bar | Deterministic |
| Size an order against MOQ and target cover | Deterministic |
| Compute arrival date, total cost, budget fit and feasibility | Deterministic |
| Order feasible offers for cheapest, fastest or balanced | Deterministic |
| Create a proposal version, a purchase request or an audit event | Deterministic action |
| Revalidate an approved proposal before writing | Deterministic action |
| Interpret "AC-003 is looking thin, sort it out" | Agentic |
| Interpret "make it cheaper" or "we cannot run out of those" | Agentic with state |
| Choose between feasible offers when more than one works | Agentic, constrained to the feasible set |
| Explain the trade-off being made, citing evidence IDs | Agentic |
| Explain what is blocking a case and what would unblock it | Agentic |

The LLM may interpret intent, select from options the tools have already declared valid, and explain results. It must not perform arithmetic, judge freshness, filter vendors, decide budget fit, or state any product, stock, price, date or vendor fact that did not come from a tool result in the current case.

### Locked parameters

These are configuration, not model judgement. Each is validated against the starter dataset.

| Parameter | Value | Rationale |
|---|---|---|
| `as_of` | injected, defaults to `2026-08-30T09:00:00` | The starter dataset is anchored to 30 Aug. A wall-clock default would make every case stale. |
| `stale_threshold_hours` | 48 | Matches the policy document. |
| `velocity_window_days` | 30 | Mean of daily units over the window, including zero-sale days. |
| `min_days_history` | 21 | Below this, velocity is not trusted. |
| `risk_threshold_days` | 10 | Cover at or above this is healthy. |
| `target_cover_days` | 30 | Order sizing target, measured from arrival date. Overridable per request. |
| `arrival_safety_buffer_days` | 1 | Arrival must beat projected stockout by at least this margin. |
| `vendor_reliability_bar` | `on_time_rate >= 0.85` and `fill_rate >= 0.85` | Separates the three qualifying vendors from SlowShip and Shady Vendor. |
| Reorder quantity | `max(ceil(velocity × (target_cover_days + lead_time_days)) − available, moq)` | Restores target cover measured from the day stock actually lands. |
| Available stock | `on_hand − reserved + confirmed_inbound` | |
| Balanced strategy | lowest total cost among offers feasible on arrival, reliability and budget | A formula, not a judgement call. |

### Expected outcomes on the starter dataset

This table is both the acceptance criteria and the Phase 3 evaluation set. Every terminal state has exactly one fixture.

| SKU | Cover | Expected status | Cause |
|---|---|---|---|
| AC-001 | 13.3 days | `NO_ACTION` | Above the 10-day risk threshold |
| AC-002 | — | `BLOCKED` | Snapshot 79 hours old |
| AC-003 | 7.5 days | `AWAITING_APPROVAL` | V-FAST feasible at ₹14,700; V-CHEAP cheaper but arrives the day of stockout |
| AC-004 | 4.0 days | `BLOCKED` | Needs ₹39,150 against ₹15,000 remaining |
| AC-005 | — | `NEEDS_INFORMATION` | 14 days of history against a 21-day minimum |
| AC-006 | 5.0 days | `BLOCKED` | Two vendors below the reliability bar, third offer expired 29 Aug |
| REF-001, TV-001 | — | `BLOCKED` | No snapshot and no sales history |

---

## 6. Scope and Non-Goals

### Product scope

- risk assessment for a SKU and warehouse from real Inventra evidence
- explicit refusal to act on stale, missing or insufficient evidence
- vendor offer evaluation on cost, arrival, reliability and budget
- a single proposal with the trade-off stated, grounded in evidence IDs
- versioned proposals with revision on human feedback
- approval by a named human, tied to an exact proposal version
- revalidation before any write, with invalidation when conditions move
- idempotent purchase request creation
- a full audit trail per case
- natural conversation with the procurement manager throughout

### Non-goals

- demand forecasting beyond a simple moving average
- multi-echelon or network-wide inventory optimisation
- stock transfers between warehouses
- automatic approval or any write without a named human
- vendor negotiation, contracts or onboarding
- goods receipt, invoicing, payments or returns
- multi-currency and FX handling
- rebuilding the Inventra database, frontend or authentication
- role-based access control and user management
- real-time event streaming from the warehouse floor
- replacing the procurement manager's judgement on exceptions

---

## 7. Delivery Phases

### Phase 1 — Data access to tools

Build the deterministic layer and prove it without any LLM.

- the five evidence tools, the four computation tools
- typed request and response models on every tool
- structured status returns, no raised exceptions crossing the boundary
- injected `as_of` clock throughout
- unit tests per tool, plus the full expected-outcome table above driven directly through the tool layer

*This is the current delivery phase.*

### Phase 2 — Tools to Replenishment Agent

Wire the proven tools into a LangGraph agent with a human in the loop.

- `CaseState` and the SQLite checkpointer
- the graph, nodes and deterministic conditional edges
- tool binding, with the LLM restricted to the exposed tool set
- `interrupt()` at `human_review`, resumable across sessions
- proposal versioning, revision, revalidation and idempotent execution
- audit events on every state transition

### Phase 3 — Evaluation, guardrails and observability

Prove the agent behaves the same way twice.

- the expected-outcome table run as an automated eval suite, end to end
- grounding checks: every factual claim in a proposal traces to an evidence ID
- injection resistance test using the `vendors.notes` field
- refusal tests: the agent must not compute, must not invent a SKU or price, must not write without a named approver
- tracing with `trace_id` correlation across tools, nodes and audit events
- token and latency measurement per case

### Phase 4 — Interface and deployment

- a warehouse-level risk scan across all SKUs
- a reviewer interface showing the proposal, the evidence bundle and the alternatives that were rejected
- containerised deployment with configuration externalised
- runbook covering blocked cases and invalidated approvals

---

## 8. Definition of Done

### Complete product

The product is successful when:

- a procurement manager can ask about a SKU in natural language and get a grounded answer
- a case that lacks trustworthy evidence is blocked with a stated reason, never guessed through
- a healthy SKU closes with `NO_ACTION` and never enters vendor selection
- every recommendation names the vendor, quantity, cost and arrival date, and states the trade-off against the alternatives
- every factual claim in a proposal traces to an evidence ID
- no purchase request exists without a named approver and an approved proposal version
- an approval that no longer holds is invalidated rather than executed
- running the same case twice produces the same purchase request, not two
- any case can be reconstructed from its audit trail

### Phase 1 checkpoint

Phase 1 is complete when:

- each of the nine tools works and is verifiable independently
- read tools, computation tools and action tools are in separate modules
- every tool returns a typed result with an explicit status; no exception crosses the tool boundary
- freshness, sufficiency, reliability and budget checks each have a passing and a failing test
- the expected-outcome table reproduces exactly through the tool layer
- the `as_of` clock is injected everywhere and no tool calls `datetime.now()`
- no LLM is required to prove any of this

### Phase 2 checkpoint

Phase 2 is complete when:

- the agent selects the right tool for a request and calls no tool when none is needed
- all six starter SKUs reach their expected terminal status through the graph
- a proposal is produced with evidence IDs and a stated trade-off
- `interrupt()` holds the case, and the case resumes correctly in a new session
- "make it cheaper" produces `REV2` while `REV1` remains unchanged on record
- approval without a named approver is refused
- revalidation catches a budget change made between approval and execution
- replaying an approved case creates no second purchase request

### Phase 3 checkpoint

Phase 3 is complete when:

- the eval suite runs end to end and passes on every fixture
- no proposal contains a fact absent from its evidence bundle
- injected instructions in `vendors.notes` change no behaviour
- every case emits a complete, correlated trace

### Phase 4 checkpoint

Phase 4 is complete when:

- a warehouse scan ranks every SKU by risk
- a reviewer can see the rejected alternatives alongside the recommendation
- the system runs from a container with no hardcoded configuration
