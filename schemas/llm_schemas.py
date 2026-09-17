from typing import Literal, Optional
from pydantic import BaseModel, Field


class OrchestratorOutput(BaseModel):
    next_destination: Literal["inventory_agent", "stocker_agent", "needs_clarification", "out_of_scope"] = Field(
    description=(
        "Where to send the request: inventory_agent to check stock or risk; "
        "stocker_agent to restock or revise a purchase proposal; "
        "needs_clarification if a required detail (SKU or warehouse) is missing or ambiguous; "
        "out_of_scope if the request is not a stock-risk check or a restock "
        "(e.g. creating or editing products, vendors or budgets, or unrelated questions)."
    ))
    sku: Optional[str] = Field(default=None, description="Exact product SKU extracted from the request, if given.")
    warehouse_id: Optional[str] = Field(default=None, description="Warehouse extracted from the request, if given.")
    target_cover_days: Optional[int] = Field(default=None, description="Requested target days of cover, if the user specified one.")
    strategy_hint: Optional[Literal["cheapest", "fastest", "balanced"]] = Field(default=None, description="Preference for choosing among vendors: cheapest, fastest, or balanced.")
    instruction: Optional[str] = Field(default=None, description="A concise, enriched task for the chosen agent. Set when routing to an agent.")
    clarification_question: Optional[str] = Field(default=None, description="The question to ask the user. Set only when next_destination is needs_clarification.")
    decline_reason: Optional[str] = Field(default=None, description="Short, polite explanation of why the request is out of scope. Set only when next_destination is out_of_scope.")
