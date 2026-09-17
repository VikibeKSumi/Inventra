from typing import Literal, Optional
from pydantic import BaseModel, Field


class OrchestratorOutput(BaseModel):
    next_destination: Literal["inventory_agent", "stocker_agent", "needs_clarification"] = Field(
        description="Which agent should handle the request, or needs_clarification if key details are missing/ambiguous."
    )
    sku: Optional[str] = Field(default=None, description="Exact product SKU extracted from the request, if given.")
    warehouse_id: Optional[str] = Field(default=None, description="Warehouse extracted from the request, if given.")
    target_cover_days: Optional[int] = Field(default=None, description="Requested target days of cover, if the user specified one.")
    strategy_hint: Optional[str] = Field(default=None, description="Preference for choosing among vendors: cheapest, fastest, or balanced.")
    instruction: Optional[str] = Field(default=None, description="A concise, enriched task for the chosen agent. Set when routing to an agent.")
    clarification_question: Optional[str] = Field(default=None, description="The question to ask the user. Set only when next_destination is needs_clarification.")
