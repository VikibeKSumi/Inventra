from state.state import InventraState
from langgraph.graph import END


def router_orchestrator(state: InventraState):

    next_destination = state.get("next_destination").lower().stip()

    if next_destination == "inventory_agent":
        return "inventory_agent_node"
    elif next_destination == "replenishment_agent":
        return "replenishment_agent_node"
    elif next_destination == "needs_clarification":
        return "needs_clarification_node"
    elif next_destination == "out_of_scope":
        END