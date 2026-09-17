
from state.state import InventraState
from prompts.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from schemas.llm_schemas import OrchestratorOutput
from langchain_core.messages import SystemMessage


class Orchestrator():

    def __init__(self, llm):
        self.llm_orchestrator = llm.with_structured_output(OrchestratorOutput)

    def call_orchestrator(self, state: InventraState):

        history = state["messages"]
        messages = [
            SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
            *history
        ]

        response = self.llm_orchestrator.invoke(input=messages)

        return {
            "next_destination": response.next_destination,
            "instruction": response.instruction,
            "clarification_question": response.clarification_question,
            "sku": response.sku,
            "warehouse_id": response.warehouse_id,
            "target_cover_days": response.target_cover_days,
            "strategy_hint": response.strategy_hint
        }