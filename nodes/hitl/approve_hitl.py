


from langgraph.types import interrupt
from state.state import InventraState
from capabilities.repository.clock import Clock
from config.config import DeterministicConfig


class ApproveHITL():

    def __init__(self, clock: Clock, config: DeterministicConfig):
        self.clock = clock
        self.MAX_REVISION = config.max_revision

    def approve_hitl(self, state: InventraState):
        revision_count = 0
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
        approver = response.get("approver")

        if not approver: 
            raise ValueError("Approver is needed. Please enter one.")
        if decision not in options:
            raise ValueError(f"Got wrong decision {decision!r}. Select from one of the following: approve, revise or reject")
        if decision == "approve":
            approved_at = self.clock.now()
        elif decision == "revise":
            revision_count = (state.get("revision_count") or 0) + 1
            if revision_count > self.MAX_REVISION:
                decision = "max_revision_crossed"
        
        # command shape
        return {
            "approver": approver,
            "decision": decision,
            "comment": response.get("comment"),
            "proposal_revision": response.get("proposal_revision"),
            "approved_at": approved_at,
            "revision_count": revision_count,
        }