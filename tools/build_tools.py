
from langchain_core.tools import tool
from capabilities.capabilities import CapabilityService
from schemas.tool_schemas import (
    GetProductInput
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
        return service.get_product(GetProductInput(sku=sku)).model_dump(mode='json')
        
    