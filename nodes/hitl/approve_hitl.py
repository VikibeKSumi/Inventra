


from langgraph.types import interrupt
from state.state import InventraState
from capabilities.repository.clock import Clock

class ApproveHITL():

    def __init__(self, clock: Clock):
        self.clock = clock

    def approve_hitl(self, state: InventraState):

        proposal = state.get("replenishment_proposal")
        details = {
            "sku": state.get("sku"),
            "warehouse_id": state.get("warehouse_id"),
            "vendor_id": state.get("vendor_id"),
            "offer_id": state.get("offer_id"),
            "quantity": state.get("quantity"), 
            "unit_price": state.get("unit_price"),
            "total_cost": state.get("total_cost"),
            "expected_arrival": state.get("expected_arrival")
        }
        options = ["approve", "revise", "reject"]

        response = interrupt({
            "proposal": proposal,
            "details": details,
            "options": options,
        })

        approved_at = None
        decision = response.get("decision")
        if decision not in options:
            raise ValueError(f"Got wrong decision {decision!r}. Select from one of the following: approve, revise or reject")
        if decision == "approve":
            approved_at = self.clock.now()
        
        # command shape
        return {
            "approver": response.get("approver"),
            "decision": decision,
            "comment": response.get("comment"),
            "proposal_revision": response.get("proposal_revision"),
            "approved_at": approved_at
        }