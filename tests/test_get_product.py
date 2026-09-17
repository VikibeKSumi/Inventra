from schemas.tool_schemas import GetProductInput
from capabilities.capabilities import CapabilityService
from capabilities.repository.clock import Clock
from config.config import config
from datetime import datetime, timezone


def test_get_product_found(service):
    result = service.get_product(GetProductInput(sku="AC-001"))

    assert result.success is True
    assert result.result_code == "OK"
    assert result.payload is not None
    assert result.payload.sku == "AC-001"
    assert result.payload.active is True
    assert len(result.evidence) == 1          # the product row was cited


def test_get_product_not_found(service):
    result = service.get_product(GetProductInput(sku="DOES-NOT-EXIST"))

    assert result.success is False
    assert result.result_code == "NOT_FOUND"
    assert result.payload is None
    assert result.evidence == ()              # nothing read, nothing cited


class FakeRepo:
    def get_product(self, sku):
        return {"sku": sku, "name": "Old Cooler", "category": "cooling", "active": 0}

def test_get_product_inactive():
    service = CapabilityService(
        repository=FakeRepo(),
        clock=Clock(as_of=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)),
        config=config,
    )
    result = service.get_product(GetProductInput(sku="AC-999"))
    assert result.success is False
    assert result.result_code == "INACTIVE"
