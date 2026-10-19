from langgraph.types import interrupt
from langchain_core.messages import AIMessage, HumanMessage
from state.state import InventraState


class ClarifyHITL():
        
    def call_hitl(state: InventraState):

        question = state.get("clarification_question")
        response = interrupt({"question": question})
        answer = response["answer"]

        return {
            "messages": [
                AIMessage(content=question),
                HumanMessage(content=answer),
            ],
            "clarification_question": None,
        }