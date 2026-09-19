from state.state import InventraState
from langgraph.graph import END
from typing import Optional


ORCHESTRATOR_ROUTES = {
    #next_destination : node name
    "inventory_agent": "inventory_agent_node",
    "replenishment_agent": "replenishment_agent_node",
    "needs_clarification": "clarify_hitl_node",
    "out_of_scope": "out_of_scope_node",

}


INVENTORY_ROUTES = {
    #status : node name
    "at_risk": "replenishment_agent_node",
    "healthy": END,
    "blocked": END,
    "needs_information": END
    
}

REPLENISHMENT_ROUTES = {
    # status : node name
    "awaiting_approval": "approve_hitl_node",
    "blocked": END
}

APPROVE_HITL_ROUTES = {
    #decision : nodes
    "approve": "create_purchase_node",
    "revise": "replenishment_agent_node",
    "reject": END
}

def router_orchestrator(state: InventraState) -> str:

    next_destination = state.get("next_destination")

    if next_destination not in ORCHESTRATOR_ROUTES:
        raise ValueError(f"Unknown next_destination: {next_destination!r}")

    return ORCHESTRATOR_ROUTES[next_destination]


def router_inventory_agent(state: InventraState) -> str:
    inventory_status = state.get("inventory_status")

    if inventory_status not in INVENTORY_ROUTES:
        raise ValueError(f"Unknown inventory_status: {inventory_status!r}")
        
    return INVENTORY_ROUTES[inventory_status]


def router_replenishment_agent(state: InventraState) -> str:
    replenishment_status = state.get("replenishment_status")

    if replenishment_status not in REPLENISHMENT_ROUTES:
        raise ValueError(f"Unknown replenishment_status: {replenishment_status!r}")

    return REPLENISHMENT_ROUTES[replenishment_status]


def router_approve_hitl(state: InventraState) -> str:
    decision = state.get("decision")

    if decision not in APPROVE_HITL_ROUTES:
        raise ValueError(f"Unknown decision: {decision!r}")

    return APPROVE_HITL_ROUTES[decision]