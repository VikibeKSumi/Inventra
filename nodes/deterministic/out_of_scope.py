

from state.state import InventraState
from langchain_core.messages import AIMessage

def out_of_scope(state: InventraState):

    decline_reason = state.get("decline_reason") or "That request is outside what I can help with."

    message = AIMessage(content=decline_reason)

    return {
        "messages": [message],
        "terminal_reason": "out_of_scope",
    }
