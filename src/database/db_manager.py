# infrastructure/database/db_manager.py
import logging
from typing import Optional
from database.base import BaseDatabase, DatabaseType
from database.sqlite_db import SQLiteDatabase
from database.schema import DatabaseSchema

logger = logging.getLogger(__name__)

class DatabaseManager:
    """
    Singleton manager for database connections.
    Allows easy switching between database types.
    """
    
    _instance: Optional['DatabaseManager'] = None
    _db: Optional[BaseDatabase] = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    @classmethod
    async def initialize(
        cls,
        db_type: DatabaseType = DatabaseType.SQLITE,
        **kwargs
    ) -> BaseDatabase:
        """Initialize database connection."""
        instance = cls()
        
        if instance._db is not None:
            logger.warning("Database already initialized")
            return instance._db
        
        # Create appropriate database instance
        if db_type == DatabaseType.SQLITE:
            db_path = kwargs.get('db_path', 'data/agent_memory.db')
            instance._db = SQLiteDatabase(db_path=db_path)
        elif db_type == DatabaseType.POSTGRESQL:
            # Future implementation
            raise NotImplementedError("PostgreSQL not yet implemented")
        elif db_type == DatabaseType.MYSQL:
            # Future implementation
            raise NotImplementedError("MySQL not yet implemented")
        else:
            raise ValueError(f"Unsupported database type: {db_type}")
        
        # Connect and initialize schema
        await instance._db.connect()
        await DatabaseSchema.initialize_database(instance._db)
        
        logger.info(f"✅ Database manager initialized with {db_type.value}")
        return instance._db
    
    @classmethod
    def get_db(cls) -> BaseDatabase:
        """Get current database instance."""
        instance = cls()
        if instance._db is None:
            raise RuntimeError("Database not initialized. Call initialize() first.")
        return instance._db
    
    @classmethod
    async def close(cls):
        """Close database connection."""
        instance = cls()
        if instance._db:
            await instance._db.disconnect()
            instance._db = None