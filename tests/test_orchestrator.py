# tests/test_orchestrator.py
from langchain_core.messages import SystemMessage, HumanMessage

from nodes.llm.orchestrator import Orchestrator
from schemas.llm_schemas import OrchestratorOutput
from prompts.prompts import ORCHESTRATOR_SYSTEM_PROMPT


class FakeStructuredLLM:
    """Stands in for llm.with_structured_output(...) — records what it was
    invoked with and returns a canned OrchestratorOutput."""
    def __init__(self, canned):
        self.canned = canned
        self.seen_messages = None

    def invoke(self, messages):
        self.seen_messages = messages
        return self.canned


class FakeLLM:
    def __init__(self, canned):
        self.structured = FakeStructuredLLM(canned)

    def with_structured_output(self, schema):
        return self.structured


def test_maps_response_into_state():
    canned = OrchestratorOutput(
        next_destination="inventory_agent",
        instruction="Check stock risk for SKU-1 at WH-1",
        sku="SKU-1",
        warehouse_id="WH-1",
        target_cover_days=14,
        strategy_hint=None,
        clarification_question=None,
    )
    orch = Orchestrator(FakeLLM(canned))
    state = {"messages": [HumanMessage(content="Is SKU-1 at WH-1 running low?")]}

    out = orch.call_orchestrator(state)

    assert out["next_destination"] == "inventory_agent"
    assert out["sku"] == "SKU-1"
    assert out["warehouse_id"] == "WH-1"
    assert out["target_cover_days"] == 14
    assert out["instruction"] == "Check stock risk for SKU-1 at WH-1"
    assert out["clarification_question"] is None


def test_builds_system_prompt_then_thread():
    canned = OrchestratorOutput(next_destination="needs_clarification",
                                clarification_question="Which warehouse?")
    orch = Orchestrator(FakeLLM(canned))
    thread = [HumanMessage(content="Is SKU-1 low?")]
    state = {"messages": thread}

    orch.call_orchestrator(state)

    seen = orch.llm_orchestrator.seen_messages
    assert isinstance(seen[0], SystemMessage)
    assert seen[0].content == ORCHESTRATOR_SYSTEM_PROMPT
    assert seen[1:] == thread
