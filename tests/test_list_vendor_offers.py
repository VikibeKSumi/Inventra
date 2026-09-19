# tests/test_list_vendor_offers.py
from decimal import Decimal
from schemas.capability_schemas import GetVendorOffersInput
from datetime import datetime, timezone
from capabilities.capabilities import CapabilityService
from capabilities.repository.clock import Clock
from config.config import config


def test_offers_ok_all_valid(service):
    result = service.list_vendor_offers(GetVendorOffersInput(sku="AC-001"))

    assert result.success is True
    assert result.result_code == "OK"
    assert len(result.payload) == 3                      # all 3 valid
    assert {o.vendor_id for o in result.payload} == {"V-FAST", "V-CHEAP", "V-BALANCED"}
    assert all(isinstance(o.unit_price, Decimal) for o in result.payload)
    assert result.evidence[0].source == "vendor_offers"


def test_offers_expired_excluded(service):
    result = service.list_vendor_offers(GetVendorOffersInput(sku="AC-006"))

    assert result.success is True
    assert result.result_code == "OK"
    assert len(result.payload) == 2                      # OFFER-006-3 expired 2026-08-29
    assert "OFFER-006-3" not in {o.offer_id for o in result.payload}


def test_offers_not_found(service):
    result = service.list_vendor_offers(GetVendorOffersInput(sku="NO-OFFERS-SKU"))

    assert result.success is False
    assert result.result_code == "NOT_FOUND"
    assert result.payload is None
    assert result.evidence == ()




class _AllExpiredRepo:
    def get_vendor_offers(self, sku):
        return [
            {"offer_id": "OLD-1", "vendor_id": "V-FAST", "unit_price": 200.0,
             "moq": 5, "lead_time_days": 2, "valid_until": "2026-08-01 08:00:00.000000"},
        ]

def test_offers_all_expired_returns_empty_ok():
    service = CapabilityService(
        repository=_AllExpiredRepo(),
        clock=Clock(as_of=datetime(2026, 8, 30, 9, 0, tzinfo=timezone.utc)),
        config=config,
    )
    result = service.list_vendor_offers(GetVendorOffersInput(sku="AC-001"))

    assert result.success is True           # empty is still a successful read
    assert result.result_code == "OK"
    assert result.payload == []             # all expired, none valid
    assert "expired" in result.message
