# tests/test_list_vendor_offers.py
from decimal import Decimal

from schemas.tool_schemas import GetVendorOffersInput


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
