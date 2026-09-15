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
