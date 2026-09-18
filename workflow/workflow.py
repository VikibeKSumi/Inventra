


from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import InMemorySaver

from config.config import DeterministicConfig
from state.state import InventraState
from capabilities.capabilities import CapabilityService
from nodes.llm.orchestrator import Orchestrator
from nodes.agents.inventory_agent import InventoryAgent
from nodes.agents.replenishment_agent import ReplenishmentAgent
from nodes.hitl.clarify_hitl import clarify_hitl
from nodes.deterministic.out_of_scope import out_of_scope
from workflow.router import (
    router_orchestrator, router_inventory_agent,
    router_replenishment_agent
)




class InventraGraph():

    def __init__(self, llm, service: CapabilityService, config: DeterministicConfig):
     
        self.workflow = StateGraph(InventraState)
        self.orchestrator = Orchestrator(llm=llm).call_orchestrator
        self.clarify_hitl = clarify_hitl
        self.out_of_scope = out_of_scope
        self.inventory_agent = InventoryAgent(llm=llm, service=service, config=config).call_agent
        self.replenishment_agent = ReplenishmentAgent(llm=llm, service=service, config=config).call_agent
        self.router_orchestrator = router_orchestrator
        self.router_inventory_agent = router_inventory_agent
        self.router_replenishment_agent = router_replenishment_agent
        self.checkpointer = InMemorySaver()
        self.graph = None
        
    def build_nodes(self):
        self.workflow.add_node("orchestrator_node", self.orchestrator)
        self.workflow.add_node("clarify_hitl_node", self.clarify_hitl)
        self.workflow.add_node("out_of_scope_node", self.out_of_scope)
        self.workflow.add_node("inventory_agent_node", self.inventory_agent)
        self.workflow.add_node("replenishment_agent_node", self.replenishment_agent)


    def build_edges(self):
        self.workflow.add_edge(START, "orchestrator_node")
        self.workflow.add_conditional_edges(
            "orchestrator_node",
            router_orchestrator,
            {
                "inventory_agent_node": "inventory_agent_node",
                "replenishment_agent_node": "replenishment_agent_node",
                "clarify_hitl_node": "clarify_hitl_node",
                "out_of_scope_node": "out_of_scope_node"
            })
        self.workflow.add_conditional_edges(
            "inventory_agent_node",
            router_inventory_agent,
            {
                "replenishment_agent_node": "replenishment_agent_node",
                END: END
            }
        )
        self.workflow.add_conditional_edges(
            "replenishment_agent_node",
            router_replenishment_agent,
            {
                END: END
            }
        )
        self.workflow.add_edge("clarify_hitl_node", "orchestrator_node")
        self.workflow.add_edge("out_of_scope_node", END)
                
        
    def compile_workflow(self):
        self.graph = self.workflow.compile(checkpointer=self.checkpointer)
        

    def build_graph(self):
        self.build_nodes()
        self.build_edges()
        self.compile_workflow()

        return self.graph