from src.core.interfaces import IDatabase
from typing import List, Dict, Any
import sqlite3

class SQLiteDatabase(IDatabase):
    def __init__(self, db_path: str):
        self.db_path = db_path

    def execute_query(self, query: str) -> List[Dict[str, Any]]:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                return [dict(row) for row in rows]
        except sqlite3.Error as e:
            return [{"error": str(e)}]

    def get_schema_info(self) -> str:
        schema = ""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
                tables = cursor.fetchall()
                for table in tables:
                    table_name = table[0]
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    col_names = [col[1] for col in columns]
                    col_defs = ", ".join(f"{col[1]} ({col[2]})" for col in columns)
                    schema += f"Table: {table_name}\n"
                    schema += f"  Columns: {col_defs}\n"
                    cursor.execute(f"SELECT {', '.join(col_names)} FROM {table_name} LIMIT 1;")
                    row = cursor.fetchone()
                    if row:
                        sample = {col_names[i]: row[i] for i in range(len(col_names))}
                        schema += f"  Sample row: {sample}\n"
                    schema += "\n"
                schema += (
                    "Relationships:\n"
                    "  trades.trade_id = risk_metrics.trade_id  (JOIN key)\n"
                    "  Use JOIN when a query needs columns from both tables "
                    "(e.g. desk/instrument from trades with pnl/dv01/delta/gamma/vega from risk_metrics).\n"
                )
        except sqlite3.Error as e:
            return f"Error getting schema: {str(e)}"
        return schema
