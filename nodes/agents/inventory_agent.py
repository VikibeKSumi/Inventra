
from langchain_core.messages import (
    AIMessage, ToolMessage, SystemMessage, HumanMessage
)
from langchain_core.tools import StructuredTool

from state.state import InventraState
from prompts.prompts import INVENTORY_AGENT_SYSTEM_PROMPT


class Inventory_agent():
    def __init__(self, llm):
        self.tools_list = self.get_tool_list()
        self.llm_with_tools = llm.bind_tools(self.tools_list)

    
    def get_view(self, state: InventraState) -> str:
        ...

    def get_tool_list(self) -> list[StructuredTool]:
        ...

    def run_tool_loop(self,messages:list) -> list:
        # append more 
        return messages
        

    def call_agent(self, state: InventraState):

        view = self.get_view(state)
        request = state["instruction"]

        messages = [
            SystemMessage(content=INVENTORY_AGENT_SYSTEM_PROMPT),
            HumanMessage(content=
                         f"CONTEXT: \n {view}\n\n"
                         f"Request Query: {request}")
        ]
        response = self.llm_with_tools.invoke(input=messages)
        messages.append(response)

        
        if response.tool_calls:
            messages = self.run_tool_loop(messages=messages)


        status = "" # Literal["at_risk", "healthy", "blocked", "needs_information"],
        return {
            "inventory_status": status,
            "inventory_explanation": messages[-1].content
        }



