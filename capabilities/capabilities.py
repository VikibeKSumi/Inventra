import hashlib, json

from capabilities.repository.sqlite_repository import SQLiteRepository
from capabilities.repository.clock import Clock
from schemas.tool_schemas import (
    ToolResult, 
    EvidenceRef,
    GetProductInput,
    ProductRecord

)

class CapabilityService:
    def __init__(self, repository: SQLiteRepository, clock: Clock):
        self.repository = repository      # your DB access object
        self.clock = clock                # injected clock (no datetime.now())

    def _fingerprint(self, data) -> str:
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()

    def get_product(self, request: GetProductInput) -> ToolResult[ProductRecord]:
        now = self.clock.now()
        row = self.repository.get_product(request.sku)          # dict row, or None

        # 1. not found
        if row is None:
            return ToolResult(
                success=False,
                result_code="NOT_FOUND",
                payload=None,
                message=f"No product found for SKU '{request.sku}'.",
                evidence=(),
            )

        # evidence for the row we read
        evidence = (
            EvidenceRef(
                source="products",
                record_ids=[request.sku],
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
                message=f"Product '{request.sku}' is inactive (discontinued).",
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
            message=f"Product '{request.sku}' found.",
            evidence=evidence,
        )
