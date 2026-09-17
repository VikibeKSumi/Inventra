from state.state import InventraState
from langgraph.graph import END



ROUTES = {
    "inventory_agent": "inventory_agent_node",
    "replenishment_agent": "replenishment_agent_node",
    "needs_clarification": "clarify_hitl_node",
    "out_of_scope": "out_of_scope_node",
}

def router_orchestrator(state: InventraState) -> str:

    next_destination = state.get("next_destination")

    if next_destination not in ROUTES:
        raise ValueError(f"Unknown next_destination: {next_destination}")

    return ROUTES[next_destination]