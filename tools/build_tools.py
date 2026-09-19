
from langchain_core.tools import tool
from capabilities.capabilities import CapabilityService
from schemas.capability_schemas import (
    GetProductInput, GetStockPositionInput, GetSalesVelocityInput,
    CalculateStockRiskInput, GetPolicyGuidanceInput, GetVendorOffersInput, 
    GetVendorPerformanceInput, GetBudgetPositionInput, BuildVendorOptionsInput
)

AGENT_TOOL_ACCESS = {
    "inventory_agent": {
        "get_product",
        "get_stock_position",
        "get_sales_velocity",
        "calculate_stock_risk",
    }, 
    "replenishment_agent": {
        "get_policy_guidance",
        "list_vendor_offers",
        "get_vendor_performance",
        "get_budget_position",
        "build_vendor_options",
    }
}

def build_tools(service: CapabilityService, agent: str):

    @tool(args_schema=GetProductInput)
    def get_product(sku) -> dict:
        """Resolve a single product by its exact SKU.
        Use this to confirm a product exists and is active before assessing stock or
        replenishment. Takes an exact SKU (no fuzzy/name search).

        Returns a ToolResult with:
        - OK: the product record (sku, name, category, active)
        - NOT_FOUND: no product with that SKU
        - INACTIVE: the product exists but is discontinued (do not restock)
        """
        return service.get_product(request=GetProductInput(sku=sku)).model_dump(mode='json')
        

    @tool(args_schema=GetStockPositionInput)
    def get_stock_position(sku, warehouse_id) -> dict:
        """Get the latest inventory snapshot for a SKU in a specific warehouse.

        Use this to find how much stock is on hand before assessing risk or sizing a
        reorder. Requires both the exact SKU and the warehouse.

        Returns a ToolResult with:
        - OK: the stock position (on_hand, reserved, confirmed_inbound, available_now,
        captured_at). Freshness is NOT judged here — captured_at is provided so a
        later step can check staleness.
        - NOT_FOUND: no snapshot exists for that SKU and warehouse.

        Note: available_now = on_hand - reserved. confirmed_inbound is expected stock,
        not yet available.
        """
        return service.get_stock_position(
            request=GetStockPositionInput(sku=sku, warehouse_id=warehouse_id)
        ).model_dump(mode="json")


    @tool(args_schema=GetSalesVelocityInput)                     
    def get_sales_velocity(sku, warehouse_id, lookback_days=30) -> dict:
        """Measure sales velocity (average daily units) for a SKU in a warehouse.

        Use this to learn how fast an item sells before assessing stock risk or sizing
        a reorder. Averages units sold over the given window (7, 14, or 30 days).

        Returns a ToolResult with:
        - OK: a velocity record (average_daily_units, units_sold, observed_days, window).
        - INSUFFICIENT_HISTORY: too few days of sales to trust the rate; no payload.

        Missing sales days count as zero sales, not missing data. average_daily_units
        is exact (Decimal) for downstream cover and reorder math.
        """
        return service.get_sales_velocity(
            request=GetSalesVelocityInput(
                sku=sku, warehouse_id=warehouse_id, lookback_days=lookback_days
            )
        ).model_dump(mode="json")


    @tool(args_schema=CalculateStockRiskInput)
    def calculate_stock_risk(sku, warehouse_id) -> dict:
        """Assess stock-out risk for a SKU in a warehouse.

        Combines current stock and sales velocity into a risk verdict: days of cover,
        projected stockout date, and at_risk vs healthy. Gathers the evidence itself.

        Returns a ToolResult with:
        - OK: a risk assessment (available_now, average_daily_units, days_of_cover,
        projected_stockout_at, risk_status).
        - NOT_FOUND: product or stock snapshot missing.
        - DATA_STALE: snapshot older than the freshness limit.
        - INSUFFICIENT_HISTORY: not enough sales history to trust the rate.
        """
        return service.calculate_stock_risk(
            request=CalculateStockRiskInput(sku=sku, warehouse_id=warehouse_id)
        ).model_dump(mode="json")


    @tool(args_schema=GetPolicyGuidanceInput)
    def get_policy_guidance(sku, warehouse_id, target_cover_days) -> dict:
        """Retrieve the company replenishment policy the proposal must follow.

        Use this before recommending a purchase, to ground the proposal in policy
        (reliability bar, target cover, buying rules). Returns the guidance to read
        and comply with — you do not enforce thresholds yourself; the tools do.

        Returns a ToolResult with:
        - OK: policy guidance (summary, full_text, source_path, policy_version).
        - NOT_FOUND: the policy document is missing.
        - INVALID_DATA: the policy is malformed (missing version/summary header).
        """
        return service.get_policy_guidance(
            request=GetPolicyGuidanceInput(
                sku=sku, warehouse_id=warehouse_id, target_cover_days=target_cover_days
            )
        ).model_dump(mode="json")


    @tool(args_schema=GetVendorOffersInput)
    def list_vendor_offers(sku) -> dict:
        """List currently valid vendor offers for a SKU.

        Use this to see who can supply the item and on what terms (price, MOQ, lead time,
        validity). Expired offers are excluded automatically.

        Returns a ToolResult with:
        - OK: a list of valid offers (offer_id, vendor_id, unit_price, moq, lead_time_days, valid_until).
        May be empty if all offers are expired (the message notes how many were excluded).
        - NOT_FOUND: the SKU has no vendor offers at all.

        Lists offers only — it does not score vendors or size/price an order; that's
        get_vendor_performance and build_vendor_options.
        """
        return service.list_vendor_offers(
            request=GetVendorOffersInput(sku=sku)
        ).model_dump(mode="json")


    @tool(args_schema=GetVendorPerformanceInput)
    def get_vendor_performance(vendor_ids: list[str]) -> dict:
        """Get reliability metrics for a set of vendors.

        Use this to check vendor performance (on-time rate, fill rate, quality) before
        recommending an offer. Pass the vendor IDs from the offers you're considering.

        Returns a ToolResult with:
        - OK: a list of vendor performance records (on_time_rate, fill_rate, quality_score, active).
        Vendors with no record are noted in the message.
        - NOT_FOUND: none of the requested vendors have performance records.

        Reports the scores only — it does not apply the reliability bar or exclude vendors;
        that happens in build_vendor_options.
        """
        return service.get_vendor_performance(
            request=GetVendorPerformanceInput(vendor_ids=vendor_ids)
        ).model_dump(mode="json")


    @tool(args_schema=GetBudgetPositionInput)
    def get_budget_position(warehouse_id) -> dict:
        """Get the remaining monthly budget for a warehouse.

        Use this before proposing a purchase, to check what a new order must fit under.
        The month is taken from the system clock; you only pass the warehouse.

        Returns a ToolResult with:
        - OK: the budget position (budget_amount, spent_amount, committed_amount, remaining_budget).
        - NOT_FOUND: no budget exists for this warehouse in the current month.

        remaining_budget = budget_amount - spent_amount - committed_amount. It reports the
        numbers only; it does not decide whether an order fits (that's build_vendor_options).
        """
        return service.get_budget_position(
            request=GetBudgetPositionInput(warehouse_id=warehouse_id)
        ).model_dump(mode="json")


    @tool(args_schema=BuildVendorOptionsInput)
    def build_vendor_options(sku, warehouse_id, target_cover_days) -> dict:
        """Build fully-costed, feasibility-checked replenishment options for a SKU.

        Use this once a SKU is at risk, to see the actual buying options. It gathers risk,
        offers, vendor performance, and budget itself, then for each offer computes the
        order quantity (to target cover, respecting MOQ), total cost, expected arrival,
        and whether it's feasible.

        Returns a ToolResult with:
        - OK: a list of options, each with proposed_quantity, total_cost, expected_arrival,
        eligible, and rejection_reasons. Pick from the ELIGIBLE ones only.
        - OVER_BUDGET: options exist but the only blocker is budget.
        - NO_VALID_OFFER: no feasible option (unreliable vendors, late arrival, etc.).
        - NOT_FOUND / DATA_STALE / INSUFFICIENT_HISTORY: propagated from the risk check.

        It sizes, prices, and vets every offer but does NOT choose one — you select from the
        eligible options and explain the trade-off.
        """
        return service.build_vendor_options(
            request=BuildVendorOptionsInput(
                sku=sku, warehouse_id=warehouse_id, target_cover_days=target_cover_days
            )
        ).model_dump(mode="json")

    tools_list = [
        get_product, get_stock_position, get_sales_velocity,
        calculate_stock_risk, get_policy_guidance, list_vendor_offers,
        get_vendor_performance, get_budget_position, build_vendor_options]

    if agent not in AGENT_TOOL_ACCESS:
        raise ValueError(f"Unknown agent {agent}. Valid:{sorted(AGENT_TOOL_ACCESS)}")

    tools_allowed = AGENT_TOOL_ACCESS[agent]
    tools_granted = [tool for tool in tools_list if tool.name in tools_allowed]

    if len(tools_granted) != len(tools_allowed):
        missing = tools_allowed - {tool.name for tool in tools_granted}
        raise ValueError(f"AGENT_TOOL_ACCESS[{agent}] names unknown tools: {sorted(missing)}")
    
    
    return tools_granted