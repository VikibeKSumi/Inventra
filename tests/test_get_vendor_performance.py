
from decimal import Decimal
from schemas.capability_schemas import GetVendorPerformanceInput



def test_perf_ok_all_found(service):
    result = service.get_vendor_performance(
        GetVendorPerformanceInput(vendor_ids=["V-FAST", "V-CHEAP"])
    )

    assert result.success is True
    assert result.result_code == "OK"
    assert len(result.payload) == 2
    assert {p.vendor_id for p in result.payload} == {"V-FAST", "V-CHEAP"}
    assert all(isinstance(p.on_time_rate, Decimal) for p in result.payload)
    assert result.evidence[0].source == "vendors"


def test_perf_some_missing_still_ok(service):
    result = service.get_vendor_performance(
        GetVendorPerformanceInput(vendor_ids=["V-FAST", "V-GHOST"])
    )

    assert result.success is True
    assert result.result_code == "OK"
    assert len(result.payload) == 1                 # only V-FAST exists
    assert "V-GHOST" in result.message              # missing one is noted


def test_perf_not_found(service):
    result = service.get_vendor_performance(
        GetVendorPerformanceInput(vendor_ids=["V-GHOST"])
    )

    assert result.success is False
    assert result.result_code == "NOT_FOUND"
    assert result.payload is None
