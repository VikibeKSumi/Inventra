# Inventra — Agentic Warehouse Stockout Resolution

Inventra is a multi-agent system that helps an inventory manager prevent avoidable stockouts. For a single SKU in a single warehouse, it investigates whether stock is at risk, prepares a grounded replenishment proposal, pauses for human approval, and safely creates a purchase request — all from evidence already sitting in the company's systems, never from guesswork.

# The problem
Keeping products in stock means constantly checking stock levels, sales pace, vendor offers, vendor reliability, and remaining budget — by hand, across separate screens. Risk gets noticed too late, decisions are inconsistent and undocumented, and by the time a shortage is spotted the fastest vendor may be gone. The result is lost sales from under-ordering or locked capital and blown budgets from over-ordering.

# What it does
Given a request like "Is AC-001 at risk in Delhi, and if so, restock it," the system:

- Interprets the request and routes it to the right specialist.
- Assesses risk from live evidence (stock, sales velocity, days of cover) and stops early if stock is healthy.
- Builds a proposal by evaluating every valid vendor offer on cost, arrival time, reliability, and budget, then recommends one with the trade-off stated explicitly.
- Waits for a named human to approve, revise, or reject.
- Revalidates the approved proposal against current data and creates exactly one purchase request, safely.

If evidence is stale, missing, insufficient, or no vendor is feasible, the case is blocked with a clear reason rather than pushed through on bad data.

# How it works
- Orchestrator (router): interprets the request, extracts the structured parameters, and routes to the right agent (or asks the human for missing details).
- Inventory-risk agent: gathers evidence and reports a risk verdict. It only reads and explains; it never decides the next step.
- Replenishment agent: turns an at-risk case into a costed, policy-compliant proposal, selecting from tool-validated feasible options.
- Human-in-the-loop: a durable approval pause that resumes across sessions.
- Deterministic execution: revalidation and the idempotent purchase-request write happen in plain code, after approval.

# Design principles
- Grounded, not guessed. Every fact, number, and verdict comes from typed tools. The LLM only interprets intent, selects among options the tools have already validated, and explains — it never computes or invents values.
- Least privilege. Each agent is given only the tools its role needs.
- Fail closed. Bad, missing, or stale evidence blocks the case with a stated reason instead of producing a risky decision.
- Safe writes. No purchase is created without a named human approval, a fresh revalidation, and an idempotency guard that prevents duplicate orders.
- Auditable. Typed shared state and evidence-ID tracking make every decision reconstructable.

# Stack
Python · LangGraph · Pydantic · SQLite

# Features
- 

# Graph Worflow
```mermaid
---
config:
  flowchart:
    curve: linear
---
graph TD;
	__start__([<p>__start__</p>]):::first
	orchestrator_node(orchestrator_node)
	clarify_hitl_node(clarify_hitl_node)
	out_of_scope_node(out_of_scope_node)
	inventory_agent_node(inventory_agent_node)
	replenishment_agent_node(replenishment_agent_node)
	approve_hitl_node(approve_hitl_node)
	create_purchase_request_node(create_purchase_request_node)
	__end__([<p>__end__</p>]):::last
	__start__ --> orchestrator_node;
	approve_hitl_node -.-> __end__;
	approve_hitl_node -.-> create_purchase_request_node;
	approve_hitl_node -.-> replenishment_agent_node;
	clarify_hitl_node --> orchestrator_node;
	inventory_agent_node -.-> __end__;
	inventory_agent_node -.-> replenishment_agent_node;
	orchestrator_node -.-> clarify_hitl_node;
	orchestrator_node -.-> inventory_agent_node;
	orchestrator_node -.-> out_of_scope_node;
	orchestrator_node -.-> replenishment_agent_node;
	replenishment_agent_node -.-> __end__;
	replenishment_agent_node -.-> approve_hitl_node;
	create_purchase_request_node --> __end__;
	out_of_scope_node --> __end__;
	classDef default fill:#f2f0ff,line-height:1.2
	classDef first fill-opacity:0
	classDef last fill:#bfb6fc
```