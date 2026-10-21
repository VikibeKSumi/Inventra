import operator
from decimal import Decimal
from datetime import date, datetime
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict, Required, NotRequired

from langgraph.graph.message import add_messages
from schemas.capability_schemas import EvidenceRef


class SeedState(TypedDict, total=False):
    messages: Required[Annotated[list, add_messages]]      # seeded, then accumulated
    case_id: NotRequired[str]
    thread_id: NotRequired[str]
    trace_id: NotRequired[str]


class SharedState(TypedDict, total=False):
    # Accumulators
    evidence: Annotated[list[EvidenceRef], operator.add]

    # Control
    revision_count: int
    retry_count: int
    
    # Graph Outcome
    status: str
    error_code: str
    purchase_request_id: str
    terminal_reason: str
    final_response: str


class OrchestratorNodeOutput(TypedDict, total=False):
    # Routing field
    next_destination: Literal[
        "inventory_agent", "replenishment_agent",
        "needs_clarification", "out_of_scope"
    ]
    # Payload
    instruction: Optional[str]
    clarification_question: Optional[str]
    sku: Optional[str]
    warehouse_id: Optional[str]
    target_cover_days: Optional[int]
    strategy_hint: Optional[str]
    # Explanation
    decline_reason: Optional[str]


class InventoryAgentOutput(TypedDict, total=False):
    # Routing field
    inventory_status: Literal[
        "at_risk", "healthy",
        "blocked", "needs_information"
    ]
    # Payload
    # ...
    # Explanation
    inventory_explanation: str 


class ReplenishmentAgentOutput(TypedDict, total=False):
    # Routing field
    replenishment_status: Literal[
        "awaiting_approval", "blocked"
    ]
    # Payload
    vendor_id: str
    offer_id: str
    quantity: int
    unit_price: Decimal
    total_cost: Decimal
    expected_arrival: date
    # Explanation
    replenishment_proposal: str


class ApprovalHITLOutput(TypedDict, total=False):
    # Routing field
    decision: Literal[
        "approve", "revise", 
        "reject", "max_revision_crossed"
    ]
    # Payload
    approver: str
    comment: str
    proposal_revision: str
    approved_at: datetime
    # Explanation
    # ...


class InventraState(
    SeedState,
    SharedState,
    OrchestratorNodeOutput,
    InventoryAgentOutput,
    ReplenishmentAgentOutput,
    ApprovalHITLOutput, 
    total=False
    ):

    """The shared graph state: caller seed + every node's output."""
 
    

   
   