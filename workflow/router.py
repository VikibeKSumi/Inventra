from state.state import InventraState
from langgraph.graph import END



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
    "awaiting_approval": END,
    "blocked": END
}

def router_orchestrator(state: InventraState) -> str:

    next_destination = state.get("next_destination")

    if next_destination not in ORCHESTRATOR_ROUTES:
        raise ValueError(f"Unknown next_destination: {next_destination}")

    return ORCHESTRATOR_ROUTES[next_destination]


def router_inventory(state: InventraState) -> str:
    inventory_status = state.get("inventory_status")

    if inventory_status not in INVENTORY_ROUTES:
        raise ValueError(f"Unknown inventory_status: {inventory_status!r}")
        
    return INVENTORY_ROUTES[inventory_status]


def router_replenishment(state: InventraState) -> str:
    replenishment_status = state.get("replenishment_status")

    if replenishment_status not in REPLENISHMENT_ROUTES:
        raise ValueError(f"Unknown inventory_status: {replenishment_status!r}")

    return REPLENISHMENT_ROUTES[replenishment_status]