

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
        "purchase_requests", "audit_events", "policy"
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
        "INVALID_DATA",
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


# Tool 6:
class GetVendorOffersInput(InputModel):
    sku: str = Field(description="Exact SKU whose vendor offers are requested.")

class VendorOffer(OutputModel):
    offer_id: str = Field(description="Unique identifier of this vendor offer.")
    vendor_id: str = Field(description="Vendor making the offer.")
    unit_price: Decimal = Field(description="Price per unit under this offer.")
    moq: int = Field(description="Minimum order quantity the vendor will accept.")
    lead_time_days: int = Field(description="Days from order to delivery.")
    valid_until: date = Field(description="Last day this offer is valid; expired offers are excluded.")


# Tool 7:
class GetVendorPerformanceInput(InputModel):
    vendor_ids: list[str] = Field(description="Vendor IDs to fetch performance metrics for.")

class VendorPerformance(OutputModel):
    vendor_id: str = Field(description="The vendor these metrics belong to.")
    active: bool = Field(description="Whether the vendor is currently active.")
    on_time_rate: Decimal = Field(description="Fraction of orders delivered on time (0-1).")
    fill_rate: Decimal = Field(description="Fraction of ordered quantity actually fulfilled (0-1).")
    quality_score: Decimal = Field(description="Quality rating (0-1).")


# Tool 8:
class GetBudgetPositionInput(InputModel):
    warehouse_id: str = Field(description="Warehouse whose current-month budget position is requested.")

class BudgetPosition(OutputModel):
    warehouse_id: str = Field(description="Warehouse this budget belongs to.")
    month: str = Field(description="Budget month (YYYY-MM), taken from the injected clock.")
    budget_amount: Decimal = Field(description="Total budget allocated for the month.")
    spent_amount: Decimal = Field(description="Amount already spent this month.")
    committed_amount: Decimal = Field(description="Amount committed (approved but not yet spent).")
    remaining_budget: Decimal = Field(description="Computed: budget_amount - spent_amount - committed_amount. What a new order must fit under.")


# Tool 9:
class BuildVendorOptionsInput(InputModel):
    sku: str = Field(description="Exact SKU to build replenishment options for.")
    warehouse_id: str = Field(description="Warehouse the order is for.")
    target_cover_days: int = Field(description="Days of cover the order should restore (from arrival).")


class VendorOption(OutputModel):
    offer_id: str = Field(description="The offer this option is based on.")
    vendor_id: str = Field(description="Vendor supplying it.")
    unit_price: Decimal = Field(description="Price per unit.")
    moq: int = Field(description="Vendor's minimum order quantity.")
    lead_time_days: int = Field(description="Days from order to delivery.")

    proposed_quantity: int = Field(description="Units to order: sized to restore target cover, raised to MOQ.")
    total_cost: Decimal = Field(description="proposed_quantity * unit_price.")
    expected_arrival: date = Field(description="Projected delivery date (order date + lead time).")

    projected_stock_at_arrival: Decimal = Field(description="Estimated units left when the order arrives (can be <= 0).")
    arrival_before_stockout: bool = Field(description="True if the delivery lands before stock runs out.")
    within_budget: bool = Field(description="True if total_cost fits the remaining budget.")

    eligible: bool = Field(description="True only if the offer is feasible on all counts (reliable vendor, valid, arrives in time, within budget).")
    rejection_reasons: list[str] = Field(default_factory=list, description="Why an offer is not eligible (e.g. UNRELIABLE_VENDOR, ARRIVES_AFTER_STOCKOUT, OVER_BUDGET). Empty when eligible.")



# validate
class PurchaseRequestInput(InputModel):
    case_id: str = Field(description="The case this purchase belongs to; part of the idempotency key.")
    sku: str = Field(description="Exact SKU being purchased.")
    warehouse_id: str = Field(description="Warehouse the stock is destined for.")
    vendor_id: str = Field(description="Vendor supplying the order.")
    offer_id: str = Field(description="The approved offer this order is based on; part of the idempotency key.")
    quantity: int = Field(description="Units to order, exactly as approved.")
    unit_price: Decimal = Field(description="Price per unit, exactly as approved.")
    total_cost: Decimal = Field(description="quantity * unit_price, exactly as approved.")
    approver: str = Field(description="Name of the human who approved this purchase.")
    approved_at: datetime = Field(description="When the approval was given, from the injected clock.")


class PurchaseRequestRecord(OutputModel):
    request_id: str = Field(description="Identifier of the purchase request row.")
    case_id: str = Field(description="The case this purchase belongs to.")
    sku: str = Field(description="SKU purchased.")
    warehouse_id: str = Field(description="Destination warehouse.")
    vendor_id: str = Field(description="Vendor supplying the order.")
    quantity: int = Field(description="Units ordered.")
    unit_price: Decimal = Field(description="Price per unit as written.")
    total_cost: Decimal = Field(description="Total committed cost as written.")
    status: str = Field(description="Lifecycle status of the request; PENDING on creation.")
    idempotency_key: str = Field(description="Key that makes re-running this write safe — a repeat returns this same record instead of ordering twice.")
    approved_by: str = Field(description="Human who approved it.")
    approved_at: datetime = Field(description="When it was approved.")
