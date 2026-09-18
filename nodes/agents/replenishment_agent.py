
import json
from typing import Any

from langchain_core.messages import (
   ToolMessage, SystemMessage, HumanMessage
)
from langchain_core.tools import StructuredTool

from state.state import InventraState
from capabilities.capabilities import CapabilityService
from prompts.prompts import REPLENISHMENT_AGENT_SYSTEM_PROMPT
from schemas.llm_schemas import OfferSelection
from tools.build_tools import build_tools
from config.config import DeterministicConfig

class ReplenishmentAgent():
    def __init__(self, llm, service: CapabilityService, config: DeterministicConfig, agent: str = "replenishment_agent"):
        self.service = service
        self.agent = agent
        self.llm_selector = llm.with_structured_output(OfferSelection)
        self.tools_list = self.get_tool_list()
        self.llm_with_tools = llm.bind_tools(self.tools_list)
        self.MAX_TOOL_ITERATION = config.max_tool_iterations


    def get_view(self, state: InventraState) -> dict[str, Any]:
         return {
            "sku": state.get("sku"),
            "warehouse_id": state.get("warehouse_id"),
            "target_cover_days": state.get("target_cover_days"),
            "strategy_hint": state.get("strategy_hint")
        }

    def get_tool_list(self) -> list[StructuredTool] :
        return build_tools(service=self.service, agent = self.agent)

    def run_tool_loop(self,local_messages:list) -> tuple[list, dict]:

        tools_repo = {tool.name: tool for tool in self.tools_list}
        response = local_messages[-1]
        tool_results: dict[str, dict] = {}
        iteration = 0

        while response.tool_calls and iteration < self.MAX_TOOL_ITERATION:
            for tool_call in response.tool_calls:
                tool = tools_repo.get(tool_call["name"])
                if tool is None:
                    local_messages.append(ToolMessage(
                        content=f"Unknown tool: {tool_call['name']}", tool_call_id=tool_call["id"])
                    )
                    continue
                tool_message = tool.invoke(tool_call)
                local_messages.append(tool_message)
                tool_results[tool_call["name"]] = json.loads(tool_message.content)
            response = self.llm_with_tools.invoke(input=local_messages)
            local_messages.append(response)
            iteration += 1

        return local_messages, tool_results



    def select_offer(self, local_messages: list, tool_results: dict) -> tuple[dict | None, str]:
        """Let the LLM pick ONE eligible option; code validates the choice."""
        options = (tool_results.get("build_vendor_options") or {}).get("payload") or []
        eligible = {o["offer_id"]: o for o in options if o.get("eligible")}

        if not eligible:
            return None, "No eligible option was available to choose from."

        selection = self.llm_selector.invoke(
            local_messages
            + [HumanMessage(content=
                "Choose exactly ONE option from the eligible options returned by "
                f"build_vendor_options. Eligible offer_ids: {sorted(eligible)}. "
                "Reply with that offer_id and your rationale.")]
        )

        option = eligible.get(selection.offer_id)
        if option is None:
            return None, (f"Selected offer {selection.offer_id!r} is not in the eligible set "
                          f"{sorted(eligible)}; refusing to propose it.")

        return option, selection.rationale


    def derive_status(self, tool_results: dict) -> str:
        options = tool_results.get("build_vendor_options")
        if options is None:
            return "blocked"                      # never priced -> nothing to approve

        if options["result_code"] == "OK":
            return "awaiting_approval"

        return "blocked"                          # OVER_BUDGET, NO_VALID_OFFER, or propagated

    def call_agent(self, state: InventraState):
        try:

            view = self.get_view(state=state)
            instruction = state.get("instruction")
            local_messages = [
                SystemMessage(content=REPLENISHMENT_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=
                        f"CONTEXT: {view}"
                        f"REQUEST QUERY: {instruction}"),
            ]

            response = self.llm_with_tools.invoke(input=local_messages)
            local_messages.append(response)

            
            status = "blocked"
            proposal = "No replenishment proposal was produced."
            option, rationale = None, ""

            evidence = []
            if response.tool_calls:
                seen = set()
                local_messages, tool_results = self.run_tool_loop(local_messages=local_messages)

                for r in tool_results.values():
                    for e in r.get("evidence", []):
                        key = (e["source"], e["fingerprint"])
                        if key not in seen:
                            seen.add(key)
                            evidence.append(e)

                if local_messages[-1].tool_calls:          # loop ended on the cap
                    return {
                        "replenishment_status": "blocked",
                        "replenishment_proposal": "Stopped: tool-call limit reached in Replenishment Agent before reaching a proposal.",
                        "evidence": evidence,
                    }

                status = self.derive_status(tool_results=tool_results)

                if status == "awaiting_approval":
                    option, rationale = self.select_offer(local_messages, tool_results)
                    if option is None:
                        status = "blocked"                      # invalid pick -> fail closed
                        proposal = rationale
                    else:
                        proposal = f"{local_messages[-1].content}\n\nChosen: {rationale}"
                else:
                    proposal = local_messages[-1].content

            result = {
                "replenishment_status": status,
                "replenishment_proposal": proposal,
                "evidence": evidence,
            }
            if option is not None:
                result.update({
                    "vendor_id": option["vendor_id"],
                    "offer_id": option["offer_id"],
                    "quantity": option["proposed_quantity"],
                    "unit_price": option["unit_price"],
                    "total_cost": option["total_cost"],
                    "expected_arrival": option["expected_arrival"],
                })
            return result

        except Exception as e:
            return {
                "replenishment_status": "blocked",
                "replenishment_proposal": f"Replenishment failed: {e}",
                "evidence": [],
            }
