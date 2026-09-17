from decimal import Decimal

from schemas.tool_schemas import CalculateStockRiskInput


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
