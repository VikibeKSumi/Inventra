from datetime import datetime

from schemas.tool_schemas import GetStockPositionInput


def test_get_stock_position_found(service):
    result = service.get_stock_position(
        GetStockPositionInput(sku="AC-001", warehouse_id="DEL-01")
    )

    assert result.success is True
    assert result.result_code == "OK"
    assert result.payload is not None
    assert result.payload.on_hand == 50
    assert result.payload.reserved == 10
    assert result.payload.available_now == 40          # on_hand - reserved
    assert isinstance(result.payload.captured_at, datetime)
    assert len(result.evidence) == 1                   # the snapshot row was cited
    assert result.evidence[0].source == "inventory_snapshots"
    assert result.evidence[0].observed_at == result.payload.captured_at


def test_get_stock_position_not_found(service):
    result = service.get_stock_position(
        GetStockPositionInput(sku="AC-001", warehouse_id="NO-SUCH-WH")
    )

    assert result.success is False
    assert result.result_code == "NOT_FOUND"
    assert result.payload is None
    assert result.evidence == ()                        # nothing read, nothing cited
