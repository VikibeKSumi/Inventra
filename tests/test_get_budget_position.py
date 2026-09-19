from decimal import Decimal

from schemas.capability_schemas import GetBudgetPositionInput


def test_budget_ok(service):
    result = service.get_budget_position(GetBudgetPositionInput(warehouse_id="DEL-01"))

    assert result.success is True
    assert result.result_code == "OK"
    assert result.payload.budget_amount == Decimal("50000")
    assert result.payload.spent_amount == Decimal("30000")
    assert result.payload.committed_amount == Decimal("5000")
    assert result.payload.remaining_budget == Decimal("15000")   # 50000 - 30000 - 5000
    assert result.payload.month == "2026-08"
    assert result.evidence[0].source == "monthly_budgets"


def test_budget_not_found(service):
    result = service.get_budget_position(GetBudgetPositionInput(warehouse_id="NO-WH"))

    assert result.success is False
    assert result.result_code == "NOT_FOUND"
    assert result.payload is None
