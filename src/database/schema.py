# infrastructure/database/schema.py
from typing import Dict, List

from database.base import BaseDatabase

class DatabaseSchema:
    """Central schema definition for all tables."""
    
    # Version tracking for migrations
    SCHEMA_VERSION = 1
    
    TABLES: Dict[str, str] = {
        # Schema version tracking
        "schema_version": """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
        
        # Conversations/Sessions table
        "conversations": """
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                agent_id TEXT NOT NULL,
                agent_name TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active BOOLEAN DEFAULT 1,
                metadata TEXT,  -- JSON
                UNIQUE(agent_id, id)
            )
        """,
        
        # Messages table - stores ALL conversation messages
        "messages": """
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                role TEXT NOT NULL,  -- system, user, assistant, tool
                content TEXT,
                tool_calls TEXT,  -- JSON array
                tool_results TEXT,  -- JSON array
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                sequence_number INTEGER NOT NULL,
                is_summarized BOOLEAN DEFAULT 0,
                metadata TEXT,  -- JSON
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """,
        
        # Summaries table - stores conversation summaries
        "summaries": """
            CREATE TABLE IF NOT EXISTS summaries (
                id TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                agent_id TEXT NOT NULL,
                summary_type TEXT NOT NULL,  -- short, long
                content TEXT NOT NULL,
                importance INTEGER DEFAULT 5,
                message_start_seq INTEGER NOT NULL,
                message_end_seq INTEGER NOT NULL,
                message_count INTEGER NOT NULL,
                tags TEXT,  -- JSON array
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT,  -- JSON
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """,
        
        # Agent configuration table
        "agent_configs": """
            CREATE TABLE IF NOT EXISTS agent_configs (
                agent_id TEXT PRIMARY KEY,
                agent_name TEXT,
                enable_summarization BOOLEAN DEFAULT 0,
                recent_k INTEGER DEFAULT 10,
                summarization_threshold INTEGER DEFAULT 20,
                auto_summarize BOOLEAN DEFAULT 1,
                config_json TEXT,  -- Full config as JSON
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """
    }
    
    INDEXES: List[str] = [
        # Message queries optimization
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_agent ON messages(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp DESC)",
        "CREATE INDEX IF NOT EXISTS idx_messages_sequence ON messages(conversation_id, sequence_number)",
        "CREATE INDEX IF NOT EXISTS idx_messages_summarized ON messages(conversation_id, is_summarized)",
        
        # Summary queries optimization
        "CREATE INDEX IF NOT EXISTS idx_summaries_conversation ON summaries(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_summaries_agent ON summaries(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_summaries_type ON summaries(summary_type)",
        "CREATE INDEX IF NOT EXISTS idx_summaries_importance ON summaries(importance DESC)",
        
        # Conversation queries optimization
        "CREATE INDEX IF NOT EXISTS idx_conversations_agent ON conversations(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_conversations_active ON conversations(is_active, updated_at DESC)"
    ]
    
    @classmethod
    async def initialize_database(cls, db: BaseDatabase):
        """Initialize database with schema."""
        # Create tables
        for table_name, create_sql in cls.TABLES.items():
            await db.execute(create_sql)
        
        # Create indexes
        for index_sql in cls.INDEXES:
            await db.execute(index_sql)
        
        # Set schema version
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (cls.SCHEMA_VERSION,)
        )