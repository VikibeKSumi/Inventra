
import json
from typing import Any

from langchain_core.messages import (
    AIMessage, ToolMessage, SystemMessage, HumanMessage
)
from langchain_core.tools import StructuredTool

from state.state import InventraState
from capabilities.capabilities import CapabilityService
from prompts.prompts import INVENTORY_AGENT_SYSTEM_PROMPT
from tools.build_tools import build_tools
from config.config import DeterministicConfig

class InventoryAgent():
    def __init__(self, llm, service: CapabilityService, config: DeterministicConfig, agent: str = "inventory_agent"):
        self.service = service
        self.agent = agent
        self.tools_list = self.get_tool_list()
        self.llm_with_tools = llm.bind_tools(self.tools_list)
        self.MAX_TOOL_ITERATION = config.max_tool_iterations


    def get_view(self, state: InventraState) -> dict[str, Any]:
        return {
            "sku": state.get("sku"),
            "warehouse_id": state.get("warehouse_id"),
            "target_cover_days": state.get("target_cover_days")
        }

    def get_tool_list(self) -> list[StructuredTool]:
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


    def derive_status(self, tool_results: dict) -> str:
        product = tool_results.get("get_product")
        if product and product["result_code"] in ("NOT_FOUND", "INACTIVE"):
            return "blocked"

        risk = tool_results.get("calculate_stock_risk")
        if risk is None:
            return "blocked"                      # never assessed -> cannot judge

        code = risk["result_code"]
        if code == "OK":
            return "at_risk" if risk["payload"]["risk_status"] == "at_risk" else "healthy"
        if code == "INSUFFICIENT_HISTORY":
            return "needs_information"
        return "blocked"                          # NOT_FOUND, DATA_STALE, anything else


    def call_agent(self, state: InventraState):
        try:
            view = str(self.get_view(state))
            request = state.get("instruction")

            local_messages = [
                SystemMessage(content=INVENTORY_AGENT_SYSTEM_PROMPT),
                HumanMessage(content=
                            f"CONTEXT: \n {view}\n\n"
                            f"Request Query: {request}")
            ]
            response = self.llm_with_tools.invoke(input=local_messages)
            local_messages.append(response)

            status = "blocked"
            evidence = []
            if response.tool_calls:
                local_messages, tool_results = self.run_tool_loop(local_messages=local_messages)
                status = self.derive_status(tool_results=tool_results)

                evidence = [e for r in tool_results.values() for e in r.get("evidence", [])]

                if local_messages[-1].tool_calls:
                    return {
                        "inventory_status": "blocked",
                        "inventory_explanation": "Stopped: tool-call limit reached in Inventory Agent before reaching a conclusion",
                        "evidence": evidence
                    }
                
            return {
                "inventory_status": status,
                "inventory_explanation": local_messages[-1].content,
                "evidence": evidence
            }


        except Exception as e: 
            return {
                "inventory_status": "blocked",
                "inventory_explanation": f"Inventory check failed: {e}",
                "evidence": []
            }

