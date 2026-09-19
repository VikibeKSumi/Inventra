## The problem

A warehouse loses money in two directions. Order too little and sales walk out the door; order too much and capital sits on a shelf while the monthly budget is gone.

Staying between those two is manual work. Someone has to know what is on hand, how fast it is moving, which vendors can supply it, which of those vendors actually deliver on time, and what budget is left - each in a different place. So risk is usually noticed late, the decision is made under time pressure, and the reasoning behind it is never written down. By the time a shortage is obvious, the vendor who could have fixed it in two days is no longer an option.


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

---

See [ARCHITECTURE.md](ARCHITECTURE.md) for the module layout.
