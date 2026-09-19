
from decimal import Decimal

from state.state import InventraState
from capabilities.capabilities import CapabilityService
from schemas.capability_schemas import PurchaseRequestInput


class PurchaseRequest():
    def __init__(self, service: CapabilityService):
        self.service = service

    def create_purchase_request(self, state: InventraState):
        try:
            sku = state.get("sku")
            warehouse_id = state.get("warehouse_id")
            case_id = state.get("case_id") or f"CASE-{sku}-{warehouse_id}"

            result = self.service.create_purchase_request(PurchaseRequestInput(
                case_id=case_id,
                sku=sku,
                warehouse_id=warehouse_id,
                vendor_id=state.get("vendor_id"),
                offer_id=state.get("offer_id"),
                quantity=state.get("quantity"),
                unit_price=Decimal(str(state.get("unit_price"))),
                total_cost=Decimal(str(state.get("total_cost"))),
                approver=state.get("approver"),
                approved_at=state.get("approved_at"),
            ))

            evidence = [e.model_dump(mode="json") for e in result.evidence]

            if not result.success:
                return {
                    "error_code": result.result_code,
                    "terminal_reason": f"write_failed:{result.result_code}",
                    "evidence": evidence,
                }

            return {
                "case_id": case_id,
                "purchase_request_id": result.payload.request_id,
                "status": result.payload.status,
                "terminal_reason": "purchase_created"
                    if result.result_code == "OK" else "purchase_already_existed",
                "evidence": evidence,
            }

        except Exception as e:
            return {
                "error_code": "WRITE_FAILED",
                "terminal_reason": f"write_failed: {e}",
                "evidence": [],
            }
