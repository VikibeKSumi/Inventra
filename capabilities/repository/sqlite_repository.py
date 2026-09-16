import sqlite3


class SQLiteRepository:
    """Read/write access to the Inventra database. Capabilities call these, never raw SQL."""

    def __init__(self, db_path: str):
        self.db_path = db_path

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row          # rows behave like dicts
        return conn

    def get_product(self, sku: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT sku, name, category, active FROM products WHERE sku = ?",
                (sku,),
            ).fetchone()
        return dict(row) if row else None


    def get_stock_position(self, sku: str, warehouse_id: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT snapshot_id, sku, warehouse_id, on_hand, reserved,
                        confirmed_inbound, captured_at
                FROM inventory_snapshots
                WHERE sku = ? AND warehouse_id = ?
                ORDER BY captured_at DESC
                LIMIT 1""",
                (sku, warehouse_id),
            ).fetchone()
        return dict(row) if row else None

    def get_sales(self, sku: str, warehouse_id: str, start: str, end: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT sale_date, units_sold FROM sales_daily
                WHERE sku = ? AND warehouse_id = ?
                    AND sale_date >= ? AND sale_date <= ?""",
                (sku, warehouse_id, start, end),
            ).fetchall()
            
        return [dict(r) for r in rows]

    def get_vendor_offers(self, sku: str) -> list[dict]:
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT offer_id, vendor_id, sku, unit_price, moq, lead_time_days, valid_until
                FROM vendor_offers WHERE sku = ?""",
                (sku,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_vendor_performance(self, vendor_ids: list[str]) -> list[dict]:
        if not vendor_ids:
            return []
        placeholders = ",".join("?" for _ in vendor_ids)
        with self._connect() as conn:
            rows = conn.execute(
                f"""SELECT vendor_id, active, on_time_rate, fill_rate, quality_score
                    FROM vendors WHERE vendor_id IN ({placeholders})""",
                tuple(vendor_ids),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_budget_position(self, warehouse_id: str, month: str) -> dict | None:
        with self._connect() as conn:
            row = conn.execute(
                """SELECT warehouse_id, month, budget_amount, spent_amount, committed_amount
                FROM monthly_budgets WHERE warehouse_id = ? AND month = ?""",
                (warehouse_id, month),
            ).fetchone()
        return dict(row) if row else None
