


import sqlite3
from pathlib import Path

def _get_db_connection(db_path: Path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn