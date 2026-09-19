from decimal import Decimal

from schemas.capability_schemas import CalculateStockRiskInput
from datetime import datetime, timezone
from capabilities.capabilities import CapabilityService
from capabilities.repository.clock import Clock
from config.config import config


def test_risk_healthy(service):
    result = service.calculate_stock_risk(
        CalculateStockRiskInput(sku="AC-001", warehouse_id="DEL-01")
    )

    assert result.success is True
    assert result.result_code == "OK"
    assert result.payload.risk_status == "healthy"          # cover 13.3 > 10
    assert result.payload.available_now == 40
    assert result.payload.average_daily_units == Decimal("3")
    assert result.payload.projected_stockout_at is not None
    assert len(result.evidence) == 2                        # stock + velocity both cited


def test_risk_at_risk(service):
    result = service.calculate_stock_risk(
        CalculateStockRiskInput(sku="AC-004", warehouse_id="DEL-01")
    )

    assert result.success is True
    assert result.result_code == "OK"
    assert result.payload.risk_status == "at_risk"          # cover 4 <= 10
    assert result.payload.days_of_cover == Decimal("4")


def test_risk_data_stale(service):
    result = service.calculate_stock_risk(
        CalculateStockRiskInput(sku="AC-002", warehouse_id="DEL-01")
    )

    assert result.success is False
    assert result.result_code == "DATA_STALE"               # snapshot ~3 days old
    assert result.payload is None


def test_risk_not_found_propagates(service):
    result = service.calculate_stock_risk(
        CalculateStockRiskInput(sku="AC-001", warehouse_id="NO-SUCH-WH")
    )

    assert result.success is False
    assert result.result_code == "NOT_FOUND"                # from get_stock_position
    assert result.payload is None


def test_risk_insufficient_history_propagates(service):
    result = service.calculate_stock_risk(
        CalculateStockRiskInput(sku="AC-005", warehouse_id="DEL-01")
    )

    assert result.success is False
    assert result.result_code == "INSUFFICIENT_HISTORY"     # from get_sales_velocity
    assert result.payload is None



class _ZeroDemandRepo:
    def get_stock_position(self, sku, warehouse_id):
        return {"snapshot_id": "SNAP-Z", "on_hand": 50, "reserved": 0,
                "confirmed_inbound": 0, "captured_at": "2026-08-30 08:30:00.000000"}  # fresh

    def get_sales(self, sku, warehouse_id, start, end):
        return [{"sale_date": f"2026-08-{d:02d}", "units_sold": 0} for d in range(1, 25)]  # 24 days, all 0

    
def test_risk_zero_demand_healthy():
    service = CapabilityService(
        repository=_ZeroDemandRepo(),
        clock=Clock(as_of=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)),
        config=config,
    )
    result = service.calculate_stock_risk(
        CalculateStockRiskInput(sku="AC-001", warehouse_id="DEL-01")
    )

    assert result.success is True
    assert result.result_code == "OK"
    assert result.payload.risk_status == "healthy"          # no demand → never runs out
    assert result.payload.days_of_cover is None
    assert result.payload.projected_stockout_at is None
    assert result.payload.average_daily_units == Decimal("0")
