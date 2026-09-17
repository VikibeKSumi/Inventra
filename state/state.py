import operator
from decimal import Decimal
from datetime import date, datetime
from typing import Annotated, Literal, Optional
from typing_extensions import TypedDict

from langgraph.graph.message import add_messages
from schemas.tool_schemas import EvidenceRef


class InventraState(TypedDict, total=False):
    messages: Annotated[list, add_messages]

    # identity
    case_id: str
    thread_id: str
    trace_id: str

    # orchestrator / request
    next_destination: Literal["inventory_agent", "stocker_agent", "needs_clarification"]
    instruction: Optional[str]
    clarification_question: Optional[str]
    sku: Optional[str]
    warehouse_id: Optional[str]
    target_cover_days: Optional[int]
    strategy_hint: Optional[str]

    # inventory agent
    inventory_status: Literal["at_risk", "healthy", "blocked", "needs_information"]
    inventory_explanation: str

    # replenishment agent
    replenishment_status: Literal["awaiting_approval", "blocked"]
    vendor_id: str
    offer_id: str
    quantity: int
    unit_price: Decimal
    total_cost: Decimal
    expected_arrival: date
    replenishment_proposal: str

    # control
    status: str
    revision_count: int
    retry_count: int
    error_code: str

    # human
    approver: str
    decision: str
    comment: str
    proposal_revision: str
    approved_at: datetime

    # outcome
    purchase_request_id: str
    terminal_reason: str

    # evidence (accumulates across nodes)
    evidence: Annotated[list[EvidenceRef], operator.add]
