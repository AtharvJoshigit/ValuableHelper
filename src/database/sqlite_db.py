# infrastructure/database/sqlite_db.py
import aiosqlite
import logging
from typing import List, Optional, Dict, Any, Tuple
from contextlib import asynccontextmanager
from database.base import BaseDatabase

logger = logging.getLogger(__name__)

class SQLiteDatabase(BaseDatabase):
    """Production-ready SQLite implementation with connection pooling."""
    
    def __init__(self, db_path: str = "data/agent_memory.db", pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._connection: Optional[aiosqlite.Connection] = None
        self._in_transaction = False
        
    async def connect(self):
        """Establish connection with optimizations."""
        if self._connection is None:
            self._connection = await aiosqlite.connect(
                self.db_path,
                timeout=30.0,
                isolation_level=None  # Autocommit mode, we'll handle transactions manually
            )
            self._connection.row_factory = aiosqlite.Row
            
            # SQLite optimizations
            await self._connection.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging
            await self._connection.execute("PRAGMA synchronous=NORMAL")  # Faster writes
            await self._connection.execute("PRAGMA cache_size=-64000")  # 64MB cache
            await self._connection.execute("PRAGMA temp_store=MEMORY")  # In-memory temp tables
            await self._connection.execute("PRAGMA mmap_size=268435456")  # 256MB memory-mapped I/O
            
            logger.info(f"✅ Connected to SQLite database: {self.db_path}")
    
    async def disconnect(self):
        """Close connection gracefully."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.info("✅ Disconnected from SQLite database")
    
    async def execute(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute a single query."""
        await self._ensure_connected()
        try:
            cursor = await self._connection.execute(query, params or ())
            if not self._in_transaction:
                await self._connection.commit()
            return cursor
        except Exception as e:
            logger.error(f"Query execution failed: {e}\nQuery: {query}")
            raise
    
    async def execute_many(self, query: str, params_list: List[Tuple]) -> Any:
        """Execute multiple queries efficiently in batch."""
        await self._ensure_connected()
        try:
            cursor = await self._connection.executemany(query, params_list)
            if not self._in_transaction:
                await self._connection.commit()
            return cursor
        except Exception as e:
            logger.error(f"Batch execution failed: {e}")
            raise
    
    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row as dictionary."""
        print(f"Fectching for query: {query} and params: {params}")
        await self._ensure_connected()
        cursor = await self._connection.execute(query, params or ())
        row = await cursor.fetchone()
        print("---Done--")
        return dict(row) if row else None
    
    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows as list of dictionaries."""
        await self._ensure_connected()
        cursor = await self._connection.execute(query, params or ())
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]
    
    async def begin_transaction(self):
        """Start an explicit transaction."""
        await self._ensure_connected()
        await self._connection.execute("BEGIN TRANSACTION")
        self._in_transaction = True
    
    async def commit(self):
        """Commit the current transaction."""
        await self._ensure_connected()
        await self._connection.commit()
        self._in_transaction = False
    
    async def rollback(self):
        """Rollback the current transaction."""
        await self._ensure_connected()
        await self._connection.rollback()
        self._in_transaction = False
    
    async def _ensure_connected(self):
        """Ensure database connection is active."""
        if self._connection is None:
            await self.connect()
    
    @asynccontextmanager
    async def transaction(self):
        """Context manager for transactions."""
        await self.begin_transaction()
        try:
            yield self
            await self.commit()
        except Exception as e:
            await self.rollback()
            logger.error(f"Transaction failed: {e}")
            raise