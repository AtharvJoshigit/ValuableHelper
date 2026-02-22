import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Any, Optional

class MemoryTool:
    def __init__(self, db_path: str = "memory.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    content TEXT NOT NULL,
                    category TEXT,
                    importance INTEGER DEFAULT 5,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT
                )
            """)

    def add_memory(self, content: str, category: str = "general", importance: int = 5, metadata: Optional[Dict] = None) -> str:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO memories (content, category, importance, metadata) VALUES (?, ?, ?, ?)",
                (content, category, importance, json.dumps(metadata or {}))
            )
        return f"Memory added: {content[:50]}..."

    def search_memory(self, query: str, limit: int = 5, min_importance: int = 1) -> List[Dict]:
        # Simple keyword search for now
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM memories WHERE content LIKE ? AND importance >= ? ORDER BY timestamp DESC LIMIT ?",
                (f"%{query}%", min_importance, limit)
            )
            return [dict(row) for row in cursor.fetchall()]
