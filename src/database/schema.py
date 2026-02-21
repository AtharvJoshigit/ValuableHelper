# database/schema.py
from typing import Dict, List
from database.base import BaseDatabase


class DatabaseSchema:
    SCHEMA_VERSION = 2

    TABLES: Dict[str, str] = {
        "schema_version": """
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,

        "conversations": """
            CREATE TABLE IF NOT EXISTS conversations (
                id          TEXT PRIMARY KEY,
                agent_id    TEXT NOT NULL,
                agent_name  TEXT,
                created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_active   BOOLEAN DEFAULT 1,
                metadata    TEXT,
                UNIQUE(agent_id, id)
            )
        """,

        # ------------------------------------------------------------------ #
        # TURNS — the primary lifecycle unit.                                 #
        # One row per (user → assistant) exchange.                            #
        # States: OPEN | COMPLETED | CANCELLED                                #
        #   OPEN      – user message received, assistant not yet finalized.   #
        #   COMPLETED – full round-trip persisted and immutable.              #
        #   CANCELLED – superseded by a new user message before completion.   #
        # ------------------------------------------------------------------ #
        "turns": """
            CREATE TABLE IF NOT EXISTS turns (
                id                   TEXT PRIMARY KEY,
                conversation_id      TEXT NOT NULL,
                agent_id             TEXT NOT NULL,
                state                TEXT NOT NULL DEFAULT 'OPEN',
                user_message_seq     INTEGER,       -- sequence_number of user msg
                assistant_message_seq INTEGER,      -- sequence_number of assistant msg
                input_tokens         INTEGER,       -- filled on completion if available
                output_tokens        INTEGER,
                is_summarized        BOOLEAN DEFAULT 0,
                created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at         TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """,

        # messages.turn_id links each message to its lifecycle owner.
        # is_summarized on the message row is kept for backward-compatible
        # queries, but authoritative archival state lives on turns.turn.is_summarized.
        "messages": """
            CREATE TABLE IF NOT EXISTS messages (
                id              TEXT PRIMARY KEY,
                conversation_id TEXT NOT NULL,
                agent_id        TEXT NOT NULL,
                turn_id         TEXT,              -- NULL for system messages
                role            TEXT NOT NULL,
                kind            TEXT NOT NULL,
                content         TEXT,
                tool_calls      TEXT,
                tool_results    TEXT,
                sequence_number INTEGER NOT NULL,
                timestamp       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                is_summarized   BOOLEAN DEFAULT 0,
                metadata        TEXT,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE,
                FOREIGN KEY (turn_id)         REFERENCES turns(id)         ON DELETE SET NULL
            )
        """,

        "summaries": """
            CREATE TABLE IF NOT EXISTS summaries (
                id                  TEXT PRIMARY KEY,
                conversation_id     TEXT NOT NULL,
                agent_id            TEXT NOT NULL,
                summary_type        TEXT NOT NULL,   -- short | long
                content             TEXT NOT NULL,
                importance          INTEGER DEFAULT 5,
                message_start_seq   INTEGER NOT NULL,
                message_end_seq     INTEGER NOT NULL,
                message_count       INTEGER NOT NULL,
                turn_start_id       TEXT,            -- first turn covered
                turn_end_id         TEXT,            -- last turn covered
                tags                TEXT,
                metadata            TEXT,
                created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
            )
        """,

        "agent_configs": """
            CREATE TABLE IF NOT EXISTS agent_configs (
                agent_id                TEXT PRIMARY KEY,
                agent_name              TEXT,
                enable_summarization    BOOLEAN DEFAULT 0,
                recent_k_turns          INTEGER DEFAULT 10,
                summarization_threshold INTEGER DEFAULT 15,
                token_threshold_pct     REAL    DEFAULT 0.70,
                auto_summarize          BOOLEAN DEFAULT 1,
                config_json             TEXT,
                created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """,
    }

    INDEXES: List[str] = [
        # Messages
        "CREATE INDEX IF NOT EXISTS idx_messages_conversation  ON messages(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_sequence      ON messages(conversation_id, sequence_number)",
        "CREATE INDEX IF NOT EXISTS idx_messages_turn          ON messages(turn_id)",
        "CREATE INDEX IF NOT EXISTS idx_messages_role          ON messages(conversation_id, role)",

        # Turns — primary retrieval patterns
        "CREATE INDEX IF NOT EXISTS idx_turns_conversation     ON turns(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_turns_state            ON turns(conversation_id, state)",
        "CREATE INDEX IF NOT EXISTS idx_turns_summarized       ON turns(conversation_id, is_summarized, state)",
        "CREATE INDEX IF NOT EXISTS idx_turns_completed_at     ON turns(conversation_id, completed_at DESC)",

        # Summaries
        "CREATE INDEX IF NOT EXISTS idx_summaries_conversation ON summaries(conversation_id)",
        "CREATE INDEX IF NOT EXISTS idx_summaries_type         ON summaries(conversation_id, summary_type)",
        "CREATE INDEX IF NOT EXISTS idx_summaries_importance   ON summaries(importance DESC)",

        # Conversations
        "CREATE INDEX IF NOT EXISTS idx_conversations_agent    ON conversations(agent_id)",
        "CREATE INDEX IF NOT EXISTS idx_conversations_active   ON conversations(is_active, updated_at DESC)",
    ]

    @classmethod
    async def initialize_database(cls, db: BaseDatabase):
        for create_sql in cls.TABLES.values():
            await db.execute(create_sql)
        for index_sql in cls.INDEXES:
            await db.execute(index_sql)
        await db.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (cls.SCHEMA_VERSION,)
        )