
from langchain_core.tools import tool
from capabilities.capabilities import CapabilityService
from schemas.tool_schemas import (
    GetProductInput, GetStockPositionInput, GetSalesVelocityInput
)


def build_tools(service: CapabilityService,):

    @tool(args_schema=GetProductInput)
    def get_product(sku):
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
    def get_stock_position(sku, warehouse_id):
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
    def get_sales_velocity(sku, warehouse_id, lookback_days=30): 
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

    

    
    tools_list = [get_product, get_stock_position, get_sales_velocity]
    return tools_list