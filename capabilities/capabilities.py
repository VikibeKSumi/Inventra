


class CapabilityService():

    def get_product(self, sku: str):
        ...


        data = {
            "sku": sku,
            "name": name,
            "category": category,
            "active": active,
        }
        
        output = ToolResult(
            ok=ok,
            code=code,
            message=message,
            evidence=evidece
            data=data,
        )
        return output