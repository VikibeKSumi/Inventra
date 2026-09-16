

from pydantic import BaseModel, Field, ConfigDict
from typing import Literal, Optional, Generic, TypeVar
from datetime import datetime
from decimal import Decimal
from datetime import date

class InputModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

class OutputModel(BaseModel):
    model_config = ConfigDict(frozen=True)


class EvidenceRef(OutputModel):
    source: Literal[
        "products", "inventory_snapshots", "sales_daily",
        "vendors", "vendor_offers", "monthly_budgets",
        "purchase_requests", "audit_events",
    ] = Field(description="Which table/dataset this fact came from — identifies the kind of record read or written.")
    record_ids: list[str] = Field(description="The exact row identifiers read from the source (e.g. snapshot_id, sku, offer_id). A list because one read can span multiple rows, such as several days of sales.")
    observed_at: Optional[datetime] = Field(default=None, description="When the fact was captured in the source system (e.g. a snapshot's captured_at). Used for freshness checks. None when the record has no real-world capture time.")
    retrieved_at: datetime = Field(description="When this system read the record. Set by us at read time; used for the audit trail, not for freshness.")
    fingerprint: str = Field(description="Hash of the record's content at read time. Re-hashing later and comparing detects whether the underlying data changed (used in revalidation).")

    

T = TypeVar("T")
class ToolResult(BaseModel, Generic[T]):
    success: bool = Field(description="Whether the tool completed its job successfully. False means the request could not be fulfilled; check result_code for why.")
    result_code: Literal[
        "OK",
        "NOT_FOUND",
        "DATA_STALE",
        "INSUFFICIENT_HISTORY",
        "NO_VALID_OFFER",
        "OVER_BUDGET",
        "APPROVAL_REQUIRED",
        "DATA_CHANGED",
        "ALREADY_EXISTS",
        "WRITE_FAILED",
        "INACTIVE"
    ] = Field(description="Machine-readable outcome code from a fixed set. Callers and routing branch on this; it names exactly what happened (success or the specific failure).")
    payload: Optional[T] = Field(default=None, description="The tool's typed result data (its per-tool schema). None when there is nothing to return, e.g. on failure.")
    message: str = Field(default="", description="Short human-readable explanation of the outcome, for logs and UI. Never parsed for control flow — that's result_code's job.")
    evidence: tuple[EvidenceRef, ...] = Field(default_factory=tuple, description="The source records this result is grounded in (IDs, timestamps, fingerprints), enabling audit and revalidation.")



# Tool 1: get_product
class GetProductInput(InputModel):
    sku: str = Field(description="Unique product identifier (stock keeping unit), e.g. 'AC-001'.")


class ProductRecord(OutputModel):
    sku: str = Field(description="Unique product identifier (stock keeping unit), e.g. 'AC-001'.")
    name: str = Field(description="Human-readable product name.")
    category: str = Field(description="Product category/group used for organizing and warehouse-wide filtering.")
    active: bool = Field(description="Whether the product is currently sellable i.e sold/stocked. False = discontinued and must not be restocked.")


# Tool 2: get_stock_position
class GetStockPositionInput(InputModel):
    sku: str = Field(description="Exact product SKU to look up stock for.")
    warehouse_id: str = Field(description="Warehouse whose stock position is requested (stock is per warehouse).")


class InventorySnapshot(OutputModel):
    on_hand: int = Field(description="Units physically in stock.")
    reserved: int = Field(description="Units already committed/allocated and therefore not available.")
    confirmed_inbound: int = Field(description="Units expected to arrive; not yet available for use.")
    available_now: int = Field(description="Units available right now, computed as on_hand - reserved.")
    captured_at: datetime = Field(description="When this snapshot was recorded by the source system (used later for freshness).")



# Tool 3: get_sales_velocity
class GetSalesVelocityInput(InputModel):
    sku: str = Field(description="Exact product SKU to measure sales for.")
    warehouse_id: str = Field(description="Warehouse whose sales history is measured (sales are per warehouse).")
    lookback_days: Literal[7, 14, 30] = Field(default=30, description="Calendar-day window to average sales over. Restricted to supported windows.")


class VelocityRecord(OutputModel):
    lookback_days: int = Field(description="Number of calendar days measured in the window (e.g. 7, 14, or 30).")
    window_start: date = Field(description="First day of the measured window (inclusive).")
    window_end: date = Field(description="Last day of the measured window (inclusive).")
    units_sold: int = Field(description="Total units sold across the window.")
    average_daily_units: Decimal = Field(description="Sales velocity: units_sold divided by lookback_days. Exact (Decimal) for downstream cover and reorder math.")
    observed_days: int = Field(description="How many days in the window actually had a sales record; compared against the minimum-history rule to judge sufficiency.")

# Tool 4: 
class CalculateStockRiskInput(InputModel):
    sku: str = Field(description="Exact product SKU.")
    warehouse_id: str = Field(description="Warehouse to assess.")

class RiskAssessment(OutputModel):
    available_now: int = Field(description="Units available now (on_hand - reserved).")
    average_daily_units: Decimal = Field(description="Sales velocity used for the calc.")
    days_of_cover: Optional[Decimal] = Field(default=None, description="Days stock will last (available / velocity). None when there's no observed demand.")
    projected_stockout_at: Optional[datetime] = Field(default=None, description="Projected date stock runs out. None when no demand.")
    risk_status: Literal["at_risk", "healthy"] = Field(description="Verdict: at_risk if days_of_cover <= risk threshold, else healthy.")


# Tool 5:
class GetPolicyGuidanceInput(InputModel):
    sku: str = Field(description="Exact product SKU the guidance applies to.")
    warehouse_id: str = Field(description="Warehouse the guidance applies to.")
    target_cover_days: int = Field(description="Target days of cover for this request, used to contextualize the guidance.")

class PolicyGuidance(OutputModel):
    summary: str = Field(description="Short summary of the applicable buying policy for this SKU/warehouse.")
    full_text: str = Field(description="The complete policy text the agent must follow when recommending.")
    source_path: str = Field(description="Where the policy came from (e.g. policy.md path), for traceability.")
    policy_version: str = Field(description="Version/identifier of the policy, so a proposal can cite which policy it followed.")



#===========ENUMS==============
class ErrorCode(str, Enum):
    """Typed error codes returned by tools."""
    NOT_FOUND = "NOT_FOUND"
    INACTIVE = "INACTIVE"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    DATA_STALE = "DATA_STALE"
    INVALID_INPUT = "INVALID_INPUT"
    UNAUTHORIZED = "UNAUTHORIZED"
    WRITE_FAILED = "WRITE_FAILED"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"



#=============SALES================

class SalesVelocity(BaseModel):
    """Result of get_sales_velocity()."""
    sku: str = Field(..., description="Product SKU")
    warehouse_id: str = Field(..., description="Warehouse identifier")
    window_7_days: float = Field(..., description="Average units sold per day, last 7 days")
    window_30_days: float = Field(..., description="Average units sold per day, last 30 days")
    observation_count_7: int = Field(..., description="Number of sales records in 7-day window")
    observation_count_30: int = Field(..., description="Number of sales records in 30-day window")
    evidence_id: str = Field(..., description="Tool evidence ID")
    retrieved_at: datetime = Field(..., description="UTC timestamp when data was retrieved")
    error: Optional[ErrorCode] = Field(None, description="Error code if lookup failed")


#==============INVENTORY===============
class ProductRecord(BaseModel):
    """Result of get_product()."""
    sku: str = Field(..., description="Product SKU")
    name: str = Field(..., description="Product name")
    category: str = Field(..., description="Product category")
    active: bool = Field(..., description="Whether product is active")
    evidence_id: str = Field(..., description="Tool evidence ID")
    retrieved_at: datetime = Field(..., description="UTC timestamp when data was retrieved")
    error: Optional[ErrorCode] = Field(None, description="Error code if lookup failed")



class StockPosition(BaseModel):
    """Result of get_stock_position()."""
    snapshot_id: str = Field(..., description="Unique inventory snapshot ID")
    sku: str = Field(..., description="Product SKU")
    warehouse_id: str = Field(..., description="Warehouse identifier")
    on_hand: int = Field(..., description="Units physically in warehouse")
    reserved: int = Field(..., description="Units reserved for other orders")
    confirmed_inbound: int = Field(..., description="Units in transit, confirmed")
    captured_at: datetime = Field(..., description="UTC timestamp when snapshot was taken")
    evidence_id: str = Field(..., description="Tool evidence ID")
    retrieved_at: datetime = Field(..., description="UTC timestamp when data was retrieved")
    error: Optional[ErrorCode] = Field(None, description="Error code if lookup failed")


class StockRisk(BaseModel):
    """Result of calculate_stock_risk() - pure deterministic calculation."""
    available_units: int = Field(..., description="on_hand - reserved + confirmed_inbound")
    daily_velocity: float = Field(..., description="Daily sales rate used (user-selected window)")
    cover_days: float = Field(..., description="Days of supply at current velocity")
    projected_stockout_date: Optional[datetime] = Field(None, description="Projected date when stock reaches 0")
    target_cover_days: int = Field(..., description="Target coverage days (user input)")
    at_risk: bool = Field(..., description="True if cover_days < target_cover_days")
    freshness_hours: float = Field(..., description="Hours since inventory snapshot was captured")
    stale: bool = Field(..., description="True if freshness_hours > 48 (2-day stale threshold)")

#===========POLICY=============
class BudgetPosition(BaseModel):
    """Result of get_budget_position()."""
    warehouse_id: str = Field(..., description="Warehouse identifier")
    month: str = Field(..., description="Month in YYYY-MM format")
    budget_amount: float = Field(..., description="Total monthly budget")
    spent_amount: float = Field(..., description="Already spent in month")
    committed_amount: float = Field(..., description="Committed via pending requests")
    remaining: float = Field(..., description="budget_amount - spent_amount - committed_amount")
    retrieved_at: datetime = Field(..., description="UTC timestamp when data was retrieved")
    evidence_id: str = Field(..., description="Tool evidence ID")
    error: Optional[ErrorCode] = Field(None, description="Error code if lookup failed")



#==============VENDORS================
class VendorOfferList(BaseModel):
    """Result of list_vendor_offers()."""
    sku: str = Field(..., description="Product SKU")
    offers: List[VendorOffer] = Field(..., description="Active, valid vendor offers")
    expired_count: int = Field(default=0, description="Number of expired offers (excluded)")
    inactive_count: int = Field(default=0, description="Number of offers from inactive vendors")
    retrieved_at: datetime = Field(..., description="UTC timestamp when data was retrieved")
    evidence_id: str = Field(..., description="Tool evidence ID")
    error: Optional[ErrorCode] = Field(None, description="Error code if lookup failed")



class VendorPerformanceList(BaseModel):
    """Result of get_vendor_performance()."""
    vendors: List[VendorPerformance] = Field(..., description="Performance metrics by vendor ID")
    retrieved_at: datetime = Field(..., description="UTC timestamp when data was retrieved")
    error: Optional[ErrorCode] = Field(None, description="Error code if lookup failed")



class StockRisk(BaseModel):
    """Result of calculate_stock_risk() - pure deterministic calculation."""
    available_units: int = Field(..., description="on_hand - reserved + confirmed_inbound")
    daily_velocity: float = Field(..., description="Daily sales rate used (user-selected window)")
    cover_days: float = Field(..., description="Days of supply at current velocity")
    projected_stockout_date: Optional[datetime] = Field(None, description="Projected date when stock reaches 0")
    target_cover_days: int = Field(..., description="Target coverage days (user input)")
    at_risk: bool = Field(..., description="True if cover_days < target_cover_days")
    freshness_hours: float = Field(..., description="Hours since inventory snapshot was captured")
    stale: bool = Field(..., description="True if freshness_hours > 48 (2-day stale threshold)")

class VendorOptionList(BaseModel):
    """Result of build_vendor_options() - pure deterministic calculation."""
    options: List[VendorOption] = Field(..., description="Comparable, sorted by cost")
    eligible_options: List[VendorOption] = Field(..., description="Options that meet deadline and reliability")
    cheapest_option: Optional[VendorOption] = Field(None, description="Lowest-cost option (may not be eligible)")
    fastest_option: Optional[VendorOption] = Field(None, description="Earliest arrival (may not be cheapest)")
    
    class Config:
        json_schema_extra = {
            "example": {
                "options": [],
                "eligible_options": [],
                "cheapest_option": None,
                "fastest_option": None,
            }
        }