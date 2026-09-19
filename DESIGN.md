# Inventra - Design

## Contents

- [The problem](#the-problem)
- [Goals](#goals)
- [How the design was derived](#how-the-design-was-derived)
  - [Step 1 - One person does everything](#step-1---one-person-does-everything)
  - [Step 2 - Split the work in two](#step-2---split-the-work-in-two)
  - [Step 3 - Automate the judgement, not the authority](#step-3---automate-the-judgement-not-the-authority)
  - [Step 4 - Decide who the humans are](#step-4---decide-who-the-humans-are)
  - [Step 5 - Scope the first version](#step-5---scope-the-first-version)
  - [Step 6 - The workflow before automation](#step-6---the-workflow-before-automation)
  - [Step 7 - Mapping to the agentic system](#step-7---mapping-to-the-agentic-system)
- [Design principles](#design-principles)
- [Trade-offs](#trade-offs)
- [Non-goals](#non-goals)



## The problem

A warehouse loses money in two directions. Order too little and sales walk out the door; order too much and capital sits on a shelf while the monthly budget is gone.

Staying between those two is manual work. Someone has to know what is on hand, how fast it is moving, which vendors can supply it, which of those vendors actually deliver on time, and what budget is left - each in a different place. So risk is usually noticed late, the decision is made under time pressure, and the reasoning behind it is never written down. By the time a shortage is obvious, the vendor who could have fixed it in two days is no longer an option.

## Goals

What this system has to get right to be worth using.

- **Every number is traceable.** A proposal states where each figure came from, and the evidence behind it can be pulled back out of the record. Nothing in a recommendation originates in the model.
- **No purchase without a named person.** A human approves, by name, before anything is written - and one approval can only ever produce one order.
- **Bad evidence stops the case.** Stale, missing or insufficient data ends the case with a stated reason. The system never fills a gap with an assumption to keep moving.
- **The same evidence gives the same outcome.** Risk verdicts, sizing, costs and feasibility are computed in code, so a case doesn't resolve differently because the model phrased itself differently.
- **A blocked case is useful.** When it can't proceed, it says exactly what was missing and what would unblock it, so a person can act instead of guessing.
- **A person can follow the reasoning.** The proposal explains the trade-off it made in plain language, not just the option it picked.

## How the design was derived

The architecture wasn't chosen from a catalogue of agent patterns. It was derived by taking an existing human workflow and asking, at each step, which parts genuinely need judgement and which are mechanical.

### Step 1 - One person does everything

A stock controller keeps a warehouse from running out. The work is routine, but it also fires on demand: a large order lands, or a manager asks for the current position on an item.

For any item that looks low, they have to:

- check what is physically on hand
- work out how fast it is selling, to know how long the stock will last
- decide which suppliers to approach, on price, speed and reliability
- apply company purchasing policy and stay inside the monthly budget
- write up a purchase plan and take it to the manager for approval

It is slow and error-prone, and it is done across many SKUs. The data already lives in the company's systems; the difficulty is the judgement layered on top of it.

### Step 2 - Split the work in two

The obvious first improvement is to separate **detection** from **action**:

- one person watches stock levels and flags what is at risk
- the other takes a flagged item and prepares the purchase

This split matters more than it looks. Detection needs stock and sales data; purchasing needs vendors, policy and budget. Two different jobs, two different sets of information - and a clean handoff between them.

### Step 3 - Automate the judgement, not the authority

The detection and proposal work is repetitive reasoning over data the company already holds. That is what the system takes over.

What it does **not** take over is the decision to spend money. Approval stays with a human, so the manager's role is unchanged: they ask for something, and they approve or reject what comes back.

### Step 4 - Decide who the humans are

Two moments genuinely need a person:

- **Clarifying the request** - if the ask is missing the item or the warehouse, guessing is worse than asking.
- **Approving the purchase** - money leaves the company, so a named person must say yes.

Everything between those two points runs without a human.

### Step 5 - Scope the first version

Deliberate simplifications, so the hard parts get built properly:

- one SKU in one warehouse per case, not a portfolio sweep
- on-demand only, triggered by a request, with no scheduled monitoring
- a single write at the end: the purchase request, nothing else

### Step 6 - The workflow before automation

Written as handoffs, the manual process is:

| Who | Role | What they do |
|---|---|---|
| Manager | asks and routes | poses the question and decides who should handle it |
| Stock checker | judges risk | reads stock and sales, decides whether the item is genuinely at risk, and hands it on or stops |
| Purchaser | prepares the buy | takes a flagged item, works through vendors, policy and budget, and brings back a proposal |
| Manager | approves | accepts, asks for a revision, or rejects |

### Step 7 - Mapping to the agentic system

The manager's job is really two jobs - *asking* and *routing*. Separating them gives the component map:

| Human role | System component |
|---|---|
| Manager asking | the user's request |
| Manager routing | **Orchestrator** - an LLM router that interprets the request and chooses the destination |
| Stock checker | **Inventory agent** - gathers evidence with tools, reports risk |
| Purchaser | **Replenishment agent** - builds and selects a costed, policy-compliant proposal |
| Manager clarifying | **Clarify HITL** - pauses and asks when a required detail is missing |
| Manager approving | **Approve HITL** - pauses for a named approval before any spend |
| Placing the order | **Create purchase request** - deterministic, idempotent, the system's only write |

The agents do what the humans did: read the evidence, interpret it, explain it. What they never do is invent a number or authorise a purchase.

## Design principles

- **Grounded, not guessed** - every fact, number and verdict comes from a typed tool. The LLM interprets intent, picks among options the tools already validated, and explains. It never computes or invents a value.
- **Agent reports, code routes** - agents write explanations; code sets the status and decides where the case goes.
- **Least privilege** - each agent gets only the tools its role needs, enforced by an allowlist.
- **Fail closed** - bad, missing or stale evidence stops the case with a stated reason instead of guessing past it.
- **Humans own the write** - no purchase without a named approval, and an idempotency key so a repeat can never place a second order.
- **Human-in-the-loop** - approval is a durable pause, checkpointed, resumable across sessions.
- **Bounded loops** - revisions are capped, so every case terminates.
- **Configuration, not constants** - thresholds live in one frozen config object; time comes from an injected clock, never `datetime.now()`.
- **Auditable** - typed shared state and evidence references make every decision reconstructable after the fact.

## Trade-offs

Decisions that could reasonably have gone the other way, and why they went this way.

**The verdict is set in code, not by the model.** The agent could have returned a status directly - simpler, one fewer step. But then the routing of a case would depend on how the model phrased itself that day. Deriving the status from tool results means the same evidence always produces the same route. The cost is that the gate walk has to be maintained alongside the tools.

**The model picks the option; code checks the pick.** Choosing between a cheaper and a faster vendor is genuine judgement, so it stays with the model. But the choice comes back as an offer id, and code confirms that id is in the eligible set before anything is written. A hallucinated or rejected offer blocks the case instead of becoming a purchase order.

**Tool loops live inside nodes, not in the graph.** Modelling the tool cycle as graph edges would make each call visible in the trace. Keeping the loop inside the node keeps the graph readable as a business workflow rather than a call log. The cost is that a node's internal retries don't show up as graph steps, and the iteration cap has to be enforced by hand.

**Revalidation was dropped from the first version.** The design calls for re-checking the proposal after approval, since data can move while a human decides. With a static seeded database nothing can change, so it would always pass. It's one node and one router to re-add, and the graph was shaped to accept it.

**Time comes from an injected clock.** Slightly more plumbing than calling `datetime.now()`, but it makes runs reproducible, lets tests pin a moment, and keeps freshness checks honest against a fixed dataset.

**Money is spent by a table constraint, not by application logic.** The idempotency check in code can lose a race. The unique constraint on the key cannot, so it is the real guarantee and the code path is just a courtesy.

## Non-goals

What this system deliberately does not do.

**It does not monitor.** Nothing runs on a schedule. A case starts because someone asked, and ends when it resolves. Continuous watching is a different system with different failure modes.

**It does not handle portfolios.** One SKU, one warehouse, one case. No "what's low across the region", no batching, no prioritising between competing shortages.

**It does not place orders.** It creates a purchase request - an internal record that something should be bought. Transmitting it to a vendor, confirming it, and tracking delivery are outside the boundary.

**It does not own its data.** Stock and sales belong to warehouse and sales operations. Inventra reads them, judges freshness, and refuses to proceed on stale evidence. It never corrects, backfills or writes to them.

**It does not decide to spend.** Every purchase needs a named human approval. There is no automatic threshold below which it approves itself, and no way for an agent to reach the write.

**It does not forecast.** Sales pace is an average over a recent window, not a model of seasonality, promotions or trends. Anything more would be a prediction presented as evidence.

---

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module layout.
