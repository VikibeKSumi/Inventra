import hashlib, json
from datetime import datetime

from capabilities.repository.sqlite_repository import SQLiteRepository
from capabilities.repository.clock import Clock
from schemas.tool_schemas import (
    ToolResult, EvidenceRef,
    GetProductInput, ProductRecord, GetStockPositionInput, InventorySnapshot
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
                success=False, result_code="NOT_FOUND", payload=None,
                message=f"No product found for SKU '{request.sku}'.", evidence=(),
            )

        # evidence for the row we read
        evidence = (
            EvidenceRef(
                source="products", record_ids=[request.sku], observed_at=None,               # products carry no capture time
                retrieved_at=now, fingerprint=self._fingerprint(row),
            ),
        )

        # 2. inactive → don't restock
        if not row["active"]:
            return ToolResult(
                success=False, result_code="INACTIVE", payload=None,
                message=f"Product '{request.sku}' is inactive (discontinued).", evidence=evidence,
            )

        # 3. found & active
        payload = ProductRecord(
            sku=row["sku"], name=row["name"],
            category=row["category"], active=row["active"],
        )
        return ToolResult(
            success=True, result_code="OK", payload=payload,
            message=f"Product '{request.sku}' found.",
            evidence=evidence,
        )


    
    def get_stock_position(self, request: GetStockPositionInput) -> ToolResult[InventorySnapshot]:
        now = self.clock.now()
        row = self.repository.get_stock_position(request.sku, request.warehouse_id)

        # not found
        if row is None:
            return ToolResult(
                success=False, result_code="NOT_FOUND", payload=None,
                message=f"No inventory snapshot for SKU '{request.sku}' in warehouse '{request.warehouse_id}'.",
                evidence=(),
            )

        captured_at = datetime.fromisoformat(row["captured_at"])   # DB stores ISO string
        available_now = row["on_hand"] - row["reserved"]

        evidence = (
            EvidenceRef(
                source="inventory_snapshots",
                record_ids=[row["snapshot_id"]],
                observed_at=captured_at,          # the snapshot's capture time
                retrieved_at=now,
                fingerprint=self._fingerprint(row),
            ),
        )

        payload = InventorySnapshot(
            on_hand=row["on_hand"],
            reserved=row["reserved"],
            confirmed_inbound=row["confirmed_inbound"],
            available_now=available_now,
            captured_at=captured_at,
        )

        return ToolResult(
            success=True, result_code="OK", payload=payload,
            message=f"Stock position for '{request.sku}' in '{request.warehouse_id}'.",
            evidence=evidence,
        )


    