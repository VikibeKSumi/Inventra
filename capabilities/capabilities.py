
from schemas.tool_schemas import (
    ToolResult, 
    EvidenceRef,
    ProductRecord

)
from datetime import datetime
import hashlib, json

class CapabilityService:
    def __init__(self, repository, clock):
        self.repository = repository      # your DB access object
        self.clock = clock                # injected clock (no datetime.now())

    def _fingerprint(self, data) -> str:
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()

    def get_product(self, sku: str) -> ToolResult[ProductRecord]:
        now = self.clock.now()
        row = self.repository.get_product(sku)          # dict row, or None

        # 1. not found
        if row is None:
            return ToolResult(
                success=False,
                result_code="NOT_FOUND",
                payload=None,
                message=f"No product found for SKU '{sku}'.",
                evidence=(),
            )

        # evidence for the row we read
        evidence = (
            EvidenceRef(
                source="products",
                record_ids=[sku],
                observed_at=None,               # products carry no capture time
                retrieved_at=now,
                fingerprint=self._fingerprint(row),
            ),
        )

        # 2. inactive → don't restock
        if not row["active"]:
            return ToolResult(
                success=False,
                result_code="INACTIVE",
                payload=None,
                message=f"Product '{sku}' is inactive (discontinued).",
                evidence=evidence,
            )

        # 3. found & active
        payload = ProductRecord(
            sku=row["sku"],
            name=row["name"],
            category=row["category"],
            active=row["active"],
        )
        return ToolResult(
            success=True,
            result_code="OK",
            payload=payload,
            message=f"Product '{sku}' found.",
            evidence=evidence,
        )
