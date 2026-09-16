import hashlib, json
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
import yaml
from datetime import date

from config.config import Config
from capabilities.repository.sqlite_repository import SQLiteRepository
from capabilities.repository.clock import Clock
from schemas.tool_schemas import (
    ToolResult, EvidenceRef,
    GetProductInput, ProductRecord, GetStockPositionInput, InventorySnapshot,
    GetSalesVelocityInput, VelocityRecord, CalculateStockRiskInput, RiskAssessment,
    GetPolicyGuidanceInput, PolicyGuidance, GetVendorOffersInput, VendorOffer,
    GetVendorPerformanceInput, VendorPerformance
)


class CapabilityService:
    def __init__(self, repository: SQLiteRepository, clock: Clock, config: Config):
        self.repository = repository     
        self.clock = clock               
        self.MIN_DAYS_HISTORY = config.min_days_history
        self.STALE_THRESHOLD_HOURS = config.stale_threshold_hours
        self.VELOCITY_WINDOW_DAYS = config.velocity_window_days
        self.RISK_THRESHOLD_DAYS = config.risk_threshold_days
        self.POLICY_PATH = config.policy_path

    def _fingerprint(self, data) -> str:
        return hashlib.sha256(
            json.dumps(data, sort_keys=True, default=str).encode()
        ).hexdigest()

    def _propagate(self, result: ToolResult) -> ToolResult:
        return ToolResult(success=False, result_code=result.result_code,
                      payload=None, message=result.message, evidence=result.evidence)


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


    def get_sales_velocity(self, request: GetSalesVelocityInput) -> ToolResult[VelocityRecord]:
        now = self.clock.now()
        end = now.date()
        start = end - timedelta(days=request.lookback_days)      # last N days (tune off-by-one to taste)

        rows = self.repository.get_sales(
            request.sku, request.warehouse_id, start.isoformat(), end.isoformat()
        )

        observed_days = len({r["sale_date"] for r in rows})     # distinct days that had a record
        units_sold = sum(r["units_sold"] for r in rows)

        evidence = (
            EvidenceRef(
                source="sales_daily",
                record_ids=[r["sale_date"] for r in rows],       # no sale_id column; use the dates
                observed_at=None,                                # sales rows have no single capture time
                retrieved_at=now,
                fingerprint=self._fingerprint(rows),
            ),
        )

        # sufficiency gate
        if observed_days < self.MIN_DAYS_HISTORY:
            return ToolResult(
                success=False, result_code="INSUFFICIENT_HISTORY", payload=None,
                message=f"Only {observed_days} days of sales history; need at least {self.config.min_days_history}.",
                evidence=evidence,
            )

        average_daily_units = Decimal(units_sold) / request.lookback_days   # missing days count as 0

        payload = VelocityRecord(
            lookback_days=request.lookback_days,
            window_start=start,
            window_end=end,
            units_sold=units_sold,
            average_daily_units=average_daily_units,
            observed_days=observed_days,
        )
        return ToolResult(
            success=True, result_code="OK", payload=payload,
            message=f"Sales velocity for '{request.sku}' over {request.lookback_days} days.",
            evidence=evidence,
        )


 
    def calculate_stock_risk(self, request: CalculateStockRiskInput) -> ToolResult[RiskAssessment]:
        now = self.clock.now()

        stock = self.get_stock_position(GetStockPositionInput(sku=request.sku, warehouse_id=request.warehouse_id))
        if not stock.success:
            return self._propagate(stock)
        snap = stock.payload

        # freshness gate
        age_hours = (now - snap.captured_at).total_seconds() / 3600
        if age_hours > self.STALE_THRESHOLD_HOURS:
            return ToolResult(success=False, result_code="DATA_STALE", payload=None,
                            message=f"Snapshot is {age_hours:.0f}h old (limit {self.STALE_THRESHOLD_HOURS}h).",
                            evidence=stock.evidence)

        vel = self.get_sales_velocity(GetSalesVelocityInput(
            sku=request.sku, warehouse_id=request.warehouse_id, lookback_days=self.VELOCITY_WINDOW_DAYS))
        if not vel.success:
            return self._propagate(vel)                                     # INSUFFICIENT_HISTORY propagates
        v = vel.payload

        available = snap.available_now
        avg = v.average_daily_units

        if avg == 0:                                       # no demand → never runs out
            days_of_cover, stockout, status = None, None, "healthy"
        else:
            days_of_cover = Decimal(available) / avg
            stockout = now + timedelta(days=float(days_of_cover))
            status = "at_risk" if days_of_cover <= self.RISK_THRESHOLD_DAYS else "healthy"

        payload = RiskAssessment(
            available_now=available, average_daily_units=avg,
            days_of_cover=days_of_cover, projected_stockout_at=stockout, risk_status=status,
        )
        return ToolResult(success=True, result_code="OK", payload=payload,
                        message=f"Risk assessed for '{request.sku}': {status}.",
                        evidence=stock.evidence + vel.evidence)   # combine both sources


    def get_policy_guidance(self, request: GetPolicyGuidanceInput) -> ToolResult[PolicyGuidance]:
        now = self.clock.now()

        try:
            raw = Path(self.POLICY_PATH).read_text(encoding="utf-8")
        except FileNotFoundError:
            return ToolResult(
                success=False, result_code="NOT_FOUND", payload=None,
                message="Policy document not found.", evidence=(),
            )

        # policy.md must start with a YAML front-matter header:
        #   ---\n version: ... \n summary: ... \n---\n <body>
        parts = raw.split("---", 2)
        if len(parts) < 3:
            return ToolResult(
                success=False, result_code="INVALID_DATA", payload=None,
                message="Policy document is missing its version/summary header.",
                evidence=(),
            )
        meta = yaml.safe_load(parts[1]) or {}
        body = parts[2].strip()

        if "version" not in meta or "summary" not in meta:
            return ToolResult(
                success=False, result_code="INVALID_DATA", payload=None,
                message="Policy header must define both 'version' and 'summary'.",
                evidence=(),
            )

        evidence = (
            EvidenceRef(
                source="policy",
                record_ids=[str(meta["version"])],
                observed_at=None,
                retrieved_at=now,
                fingerprint=self._fingerprint(raw),
            ),
        )

        payload = PolicyGuidance(
            summary=str(meta["summary"]),
            full_text=body,
            source_path=self.POLICY_PATH,
            policy_version=str(meta["version"]),
        )

        return ToolResult(
            success=True, result_code="OK", payload=payload,
            message="Policy guidance retrieved.", evidence=evidence,
        )




    def list_vendor_offers(self, request: GetVendorOffersInput) -> ToolResult[list[VendorOffer]]:
        now = self.clock.now()
        rows = self.repository.get_vendor_offers(request.sku)

        # no offers at all for this SKU
        if not rows:
            return ToolResult(
                success=False, result_code="NOT_FOUND", payload=None,
                message=f"No vendor offers for SKU '{request.sku}'.", evidence=(),
            )

        # keep only currently-valid (non-expired) offers
        valid_rows = [r for r in rows if date.fromisoformat(r["valid_until"]) >= now.date()]

        offers = [
            VendorOffer(
                offer_id=r["offer_id"],
                vendor_id=r["vendor_id"],
                unit_price=Decimal(str(r["unit_price"])),
                moq=r["moq"],
                lead_time_days=r["lead_time_days"],
                valid_until=date.fromisoformat(r["valid_until"]),
            )
            for r in valid_rows
        ]

        evidence = (
            EvidenceRef(
                source="vendor_offers",
                record_ids=[r["offer_id"] for r in valid_rows],
                observed_at=None,
                retrieved_at=now,
                fingerprint=self._fingerprint(valid_rows),
            ),
        )

        return ToolResult(
            success=True, result_code="OK", payload=offers,
            message=f"{len(offers)} valid offer(s) for '{request.sku}' ({len(rows) - len(valid_rows)} expired excluded).",
            evidence=evidence,
        )



    def get_vendor_performance(self, request: GetVendorPerformanceInput) -> ToolResult[list[VendorPerformance]]:
        now = self.clock.now()
        rows = self.repository.get_vendor_performance(request.vendor_ids)

        if not rows:
            return self._fail("NOT_FOUND", "No performance records for the requested vendors.")

        performances = [
            VendorPerformance(
                vendor_id=r["vendor_id"],
                active=r["active"],
                on_time_rate=Decimal(str(r["on_time_rate"])),
                fill_rate=Decimal(str(r["fill_rate"])),
                quality_score=Decimal(str(r["quality_score"])),
            )
            for r in rows
        ]

        evidence = (
            EvidenceRef(
                source="vendors",
                record_ids=[r["vendor_id"] for r in rows],
                observed_at=None,
                retrieved_at=now,
                fingerprint=self._fingerprint(rows),
            ),
        )

        found = {r["vendor_id"] for r in rows}
        missing = [v for v in request.vendor_ids if v not in found]
        msg = f"Performance for {len(rows)} vendor(s)."
        if missing:
            msg += f" No record for: {', '.join(missing)}."

        return ToolResult(success=True, result_code="OK", payload=performances,
                        message=msg, evidence=evidence)
