# tests/test_build_vendor_options.py
from decimal import Decimal

from schemas.tool_schemas import BuildVendorOptionsInput


def test_options_ok(service):
    result = service.build_vendor_options(
        BuildVendorOptionsInput(sku="AC-001", warehouse_id="DEL-01", target_cover_days=14)
    )

    assert result.success is True
    assert result.result_code == "OK"
    eligible = [o for o in result.payload if o.eligible]
    assert len(eligible) == 3
    fast = next(o for o in result.payload if o.vendor_id == "V-FAST")
    assert fast.proposed_quantity == 8            # ceil(3*14 - (40-3*2)) = 8, >= moq 5
    assert fast.total_cost == Decimal("2000")     # 8 * 250
    assert fast.eligible is True


def test_options_over_budget(service):
    result = service.build_vendor_options(
        BuildVendorOptionsInput(sku="AC-004", warehouse_id="DEL-01", target_cover_days=14)
    )

    assert result.success is False
    assert result.result_code == "OVER_BUDGET"
    assert all(not o.eligible for o in result.payload)
    assert all(o.rejection_reasons == ["OVER_BUDGET"] for o in result.payload)


def test_options_no_valid_offer(service):
    result = service.build_vendor_options(
        BuildVendorOptionsInput(sku="AC-006", warehouse_id="DEL-01", target_cover_days=14)
    )

    assert result.success is False
    assert result.result_code == "NO_VALID_OFFER"
    assert all("UNRELIABLE_VENDOR" in o.rejection_reasons for o in result.payload)


def test_options_propagates_not_found(service):
    result = service.build_vendor_options(
        BuildVendorOptionsInput(sku="AC-001", warehouse_id="NO-WH", target_cover_days=14)
    )

    assert result.success is False
    assert result.result_code == "NOT_FOUND"      # from the risk step
    assert result.payload is None

from datetime import datetime, timezone

from capabilities.capabilities import CapabilityService
from capabilities.repository.clock import Clock
from config.config import config

RELIABLE = {"vendor_id": "V-FAST", "active": 1,
            "on_time_rate": 0.95, "fill_rate": 0.98, "quality_score": 0.96}


class _FakeRepo:
    """Forces a single-offer scenario so one rejection reason is isolated."""
    def __init__(self, *, on_hand, avg, offer, perf, budget=100000):
        self._on_hand, self._avg = on_hand, avg
        self._offer, self._perf, self._budget = offer, perf, budget

    def get_stock_position(self, sku, warehouse_id):
        return {"snapshot_id": "S", "on_hand": self._on_hand, "reserved": 0,
                "confirmed_inbound": 0, "captured_at": "2026-08-30 08:30:00.000000"}  # fresh

    def get_sales(self, sku, warehouse_id, start, end):
        return [{"sale_date": f"2026-08-{d:02d}", "units_sold": self._avg} for d in range(1, 31)]  # 30 days

    def get_vendor_offers(self, sku):
        return [self._offer]

    def get_vendor_performance(self, vendor_ids):
        return [p for p in self._perf if p["vendor_id"] in vendor_ids]

    def get_budget_position(self, warehouse_id, month):
        return {"warehouse_id": warehouse_id, "month": month,
                "budget_amount": self._budget, "spent_amount": 0, "committed_amount": 0}


def _service(repo):
    return CapabilityService(
        repository=repo,
        clock=Clock(as_of=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)),
        config=config,
    )


def _req():
    return BuildVendorOptionsInput(sku="X", warehouse_id="W", target_cover_days=14)


def test_option_arrives_after_stockout():
    # avail 10, vel 5, lead 3 -> stock_at_arrival = 10 - 15 = -5 (<= 0)
    offer = {"offer_id": "O", "vendor_id": "V-FAST", "unit_price": 10.0,
             "moq": 5, "lead_time_days": 3, "valid_until": "2026-09-29 08:00:00.000000"}
    result = _service(_FakeRepo(on_hand=10, avg=5, offer=offer, perf=[RELIABLE])).build_vendor_options(_req())

    assert result.result_code == "NO_VALID_OFFER"
    o = result.payload[0]
    assert o.rejection_reasons == ["ARRIVES_AFTER_STOCKOUT"]
    assert o.arrival_before_stockout is False


def test_option_no_replenishment_needed():
    # avail 100, vel 1, lead 2 -> stock_at_arrival 98 >= 1*14 -> required 0 -> qty 0
    offer = {"offer_id": "O", "vendor_id": "V-FAST", "unit_price": 250.0,
             "moq": 5, "lead_time_days": 2, "valid_until": "2026-09-29 08:00:00.000000"}
    result = _service(_FakeRepo(on_hand=100, avg=1, offer=offer, perf=[RELIABLE])).build_vendor_options(_req())

    assert result.result_code == "NO_VALID_OFFER"
    o = result.payload[0]
    assert o.proposed_quantity == 0
    assert o.rejection_reasons == ["NO_REPLENISHMENT_NEEDED"]


def test_option_unknown_vendor():
    # offer references a vendor with no perf record -> p is None
    offer = {"offer_id": "O", "vendor_id": "V-GHOST", "unit_price": 10.0,
             "moq": 5, "lead_time_days": 2, "valid_until": "2026-09-29 08:00:00.000000"}
    result = _service(_FakeRepo(on_hand=10, avg=2, offer=offer, perf=[RELIABLE])).build_vendor_options(_req())

    assert result.result_code == "NO_VALID_OFFER"
    o = result.payload[0]
    assert o.rejection_reasons == ["INACTIVE_OR_UNKNOWN_VENDOR"]
