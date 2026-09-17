
from state.state import InventraState
from prompts.prompts import ORCHESTRATOR_SYSTEM_PROMPT
from schemas.llm_schemas import OrchestratorOutput
from langchain_core.messages import SystemMessage


class Orchestrator():

    def __init__(self, llm):
        self.llm_orchestrator = llm.with_structured_output(OrchestratorOutput)

    def call_orchestrator(self, state: InventraState) -> dict:

        history = state["messages"]
        messages = [
            SystemMessage(content=ORCHESTRATOR_SYSTEM_PROMPT),
            *history
        ]

        response = self.llm_orchestrator.invoke(messages)

        return {
            "next_destination": response.next_destination,
            "instruction": response.instruction,
            "clarification_question": response.clarification_question,
            "sku": response.sku,
            "warehouse_id": response.warehouse_id,
            "target_cover_days": response.target_cover_days,
            "strategy_hint": response.strategy_hint
        }


if __name__ == "__main__":
    from langchain_openai import ChatOpenAI
    from langchain_core.messages import HumanMessage
    import os
    from dotenv import load_dotenv
    load_dotenv()

    llm = ChatOpenAI(
        api_key=os.getenv("OPENAI_API_KEY"),
        model="gpt-5.4-mini"
    )

    state = {
        "messages": [
            HumanMessage(content="Is AC-004 running low at DEL-01? Should we reorder to 14 days cover?")
        ]
    }

    orchestrator = Orchestrator(llm=llm)
    response = orchestrator.call_orchestrator(state=state)
    print(response)