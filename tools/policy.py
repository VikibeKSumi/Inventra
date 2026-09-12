

import sqlite3
from pathlib import Path
from datetime import datetime
from schemas.tool_schemas import (
    BudgetPosition,
    ErrorCode
)



DB_PATH = Path("data/inventra.db")
def _get_db_connection(db_path: Path = DB_PATH):
    conn = sqlite3.connect(db_path)
    conn.row_factory =sqlite3.Row
    return conn


def get_budget_position(
    warehouse_id: str,
    budget_month: str  # YYYY-MM format
) -> BudgetPosition:
    """
    Get the latest budget position for a warehouse and month.
    
    Calculates remaining = budget - spent - committed.
    
    Args:
        warehouse_id: Warehouse identifier
        budget_month: Month in YYYY-MM format
    
    Returns:
        BudgetPosition with current spending and available budget
    """
    try:
        conn = _get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute(
            """
            SELECT budget_id, warehouse_id, month, budget_amount, 
                   spent_amount, committed_amount
            FROM monthly_budgets
            WHERE warehouse_id = ? AND month = ?
            """,
            (warehouse_id, budget_month)
        )
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return BudgetPosition(
                warehouse_id=warehouse_id,
                month=budget_month,
                budget_amount=0,
                spent_amount=0,
                committed_amount=0,
                remaining=0,
                retrieved_at=datetime.utcnow(),
                evidence_id="",
                error=ErrorCode.NOT_FOUND,
            )
        
        remaining = (
            row["budget_amount"] - 
            row["spent_amount"] - 
            row["committed_amount"]
        )
        
        return BudgetPosition(
            warehouse_id=row["warehouse_id"],
            month=row["month"],
            budget_amount=row["budget_amount"],
            spent_amount=row["spent_amount"],
            committed_amount=row["committed_amount"],
            remaining=remaining,
            retrieved_at=datetime.utcnow(),
            evidence_id=f"budget:{warehouse_id}:{budget_month}",
        )
    except Exception as e:
        return BudgetPosition(
            warehouse_id=warehouse_id,
            month=budget_month,
            budget_amount=0,
            spent_amount=0,
            committed_amount=0,
            remaining=0,
            retrieved_at=datetime.utcnow(),
            evidence_id="",
            error=ErrorCode.UNKNOWN_ERROR,
        )
