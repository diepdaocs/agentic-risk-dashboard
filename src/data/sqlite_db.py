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
                    schema += f"Table: {table_name}\n"
                    cursor.execute(f"PRAGMA table_info({table_name});")
                    columns = cursor.fetchall()
                    for col in columns:
                        schema += f"  - {col[1]} ({col[2]})\n"
        except sqlite3.Error as e:
            return f"Error getting schema: {str(e)}"
        return schema
