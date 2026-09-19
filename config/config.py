
from decimal import Decimal
from pydantic import BaseModel, ConfigDict, Field



class DeterministicConfig(BaseModel):
    model_config = ConfigDict(frozen=True)

    # freshness
    stale_threshold_hours: int = Field(default=2, description="Max snapshot age; older = DATA_STALE.")

    # demand / velocity
    velocity_window_days: int = Field(default=30, description="Default window for average daily sales.")
    min_days_history: int = Field(default=21, description="Min days of sales history to trust the rate.")

    # risk
    risk_threshold_days: int = Field(default=10, description="Days of cover at/below which a SKU is at_risk.")

    # sizing
    target_cover_days: int = Field(default=14, description="Default target days of cover to restore (range 7-45).")
    arrival_safety_buffer_days: int = Field(default=1, description="Delivery must beat stockout by this margin.")

    # vendor reliability bar (>= 0.90 per policy)
    min_on_time_rate: Decimal = Field(default=Decimal("0.90"))
    min_fill_rate: Decimal = Field(default=Decimal("0.90"))
    min_quality_score: Decimal = Field(default=Decimal("0.90"))

    # policy source
    policy_path: str = Field(default="data/policy.md", description="Path to the policy document.")


    #path
    db_path: str = Field(default="data/inventra.db", description="Path to the Inventra SQLite database")


    #inventory agent
    max_tool_iterations: int = Field(default=6, description="Max tool-loop passes per agent call.")

    max_revision: int = Field(default=3, description="Max approver-requested revisions before the case is closed unresolved.")

config = DeterministicConfig()