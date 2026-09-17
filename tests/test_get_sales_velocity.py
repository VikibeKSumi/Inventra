from decimal import Decimal

from schemas.tool_schemas import GetSalesVelocityInput


def test_get_sales_velocity_ok(service):
    result = service.get_sales_velocity(
        GetSalesVelocityInput(sku="AC-001", warehouse_id="DEL-01", lookback_days=30)
    )

    assert result.success is True
    assert result.result_code == "OK"
    assert result.payload is not None
    assert result.payload.observed_days == 30
    assert result.payload.units_sold == 90
    assert result.payload.average_daily_units == Decimal("3")   # 90 / 30
    assert len(result.evidence) == 1
    assert result.evidence[0].source == "sales_daily"


def test_get_sales_velocity_insufficient_history(service):
    result = service.get_sales_velocity(
        GetSalesVelocityInput(sku="AC-005", warehouse_id="DEL-01", lookback_days=30)
    )

    assert result.success is False
    assert result.result_code == "INSUFFICIENT_HISTORY"
    assert result.payload is None
    assert len(result.evidence) == 1        # rows were read (just too few days), so still cited
