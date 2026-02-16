from abc import ABC, abstractmethod
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum

class DatabaseType(Enum):
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"

class BaseDatabase(ABC):
    """Abstract base class for database operations."""
    
    @abstractmethod
    async def connect(self):
        """Establish database connection."""
        pass
    
    @abstractmethod
    async def disconnect(self):
        """Close database connection."""
        pass
    
    @abstractmethod
    async def execute(self, query: str, params: Optional[Tuple] = None) -> Any:
        """Execute a single query."""
        pass
    
    @abstractmethod
    async def execute_many(self, query: str, params_list: List[Tuple]) -> Any:
        """Execute multiple queries in batch."""
        pass
    
    @abstractmethod
    async def fetch_one(self, query: str, params: Optional[Tuple] = None) -> Optional[Dict[str, Any]]:
        """Fetch a single row."""
        pass
    
    @abstractmethod
    async def fetch_all(self, query: str, params: Optional[Tuple] = None) -> List[Dict[str, Any]]:
        """Fetch all rows."""
        pass
    
    @abstractmethod
    async def begin_transaction(self):
        """Start a transaction."""
        pass
    
    @abstractmethod
    async def commit(self):
        """Commit current transaction."""
        pass
    
    @abstractmethod
    async def rollback(self):
        """Rollback current transaction."""
        pass