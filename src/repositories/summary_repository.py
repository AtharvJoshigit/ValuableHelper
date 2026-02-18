# infrastructure/repositories/summary_repository.py
import json
import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
from database.base import BaseDatabase
from rag.stores.memory import MemoryVectorStore
from src.rag.schema import MemorySchema

logger = logging.getLogger(__name__)

class SummaryRepository:
    """
    Hybrid repository for Summary management.
    - SQLite: Stores metadata, exact text, and timeline (Recent/Rolling access).
    - VectorStore (Chroma): Stores embeddings for semantic search (Long-term recall).
    """

    def __init__(self, db: BaseDatabase, vector_store: Optional[MemoryVectorStore] = None):
        self.db = db
        self.vector_store = vector_store or MemoryVectorStore()

    async def add_summary(
        self,
        conversation_id: str,
        agent_id: str,
        summary_type: str,
        content: str,
        importance: int,
        message_start_seq: int,
        message_end_seq: int,
        message_count: int,
        tags: List[str],
        metadata: Dict[str, Any],
        agent_name: Optional[str] = None
    ) -> str:
        """
        Store summary in SQLite and optionally in Vector Store (for long-term recall).
        """
        summary_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # 1. SQL Insertion
        query = """
            INSERT INTO summaries (
                id, conversation_id, agent_id, summary_type, content,
                importance, message_start_seq, message_end_seq, message_count,
                tags, metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        # Ensure metadata/tags are strings for SQL
        sql_tags = json.dumps(tags) if isinstance(tags, list) else tags
        sql_metadata = json.dumps(metadata) if isinstance(metadata, dict) else metadata

        await self.db.execute(
            query,
            (
                summary_id, conversation_id, agent_id, summary_type, content,
                importance, message_start_seq, message_end_seq, message_count,
                sql_tags, sql_metadata, created_at
            )
        )

        # 2. Vector Store Insertion (Only for 'long' summaries used for RAG recall).
        # 'short' running summaries change too frequently to be worth indexing.
        if summary_type == "long" and self.vector_store:
            
            vector_metadata = {
                "summary_id": summary_id,
                "conversation_id": conversation_id,
                "start_seq": message_start_seq,
                "end_seq": message_end_seq,
                "type": summary_type,
                **metadata 
            }

            # Sanitize: vector store values must be str, int, float, or bool
            safe_vector_metadata = {
                k: json.dumps(v) if isinstance(v, (list, dict)) else v 
                for k, v in vector_metadata.items()
            }

            memory_schema = MemorySchema(
                agent_id=agent_id,
                agent_name=agent_name,
                content=content,
                role="summary",
                summary_type=summary_type,
                importance=importance,
                message_count=message_count,
                tags=tags,
                metadata=safe_vector_metadata,
                timestamp=created_at
            )
            
            self.vector_store.add_memory(memory_schema)

        logger.info(f"✅ Summary saved: {summary_type} (ID: {summary_id[:8]})")
        return summary_id

    async def get_latest_rolling_summary(self, conversation_id: str) -> Optional[str]:
        """
        Get the most recent 'short' summary for the System Prompt.
        Returns ONE row — the rolling/running summary that replaces itself on every cycle.
        """
        query = """
            SELECT content
            FROM summaries
            WHERE conversation_id = ? AND summary_type = 'short'
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = await self.db.fetch_one(query, (conversation_id,))
        return row['content'] if row else None

    async def search_semantic(
        self,
        agent_id: str,
        query_text: str,
        limit: int = 5,
        min_importance: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Retrieve relevant past summaries via Vector Search.
        Enriches results with SQL data if needed.
        """
        if not self.vector_store:
            logger.warning("No vector store configured. Falling back to SQL search.")
            return await self.search_sql(agent_id, query_text, limit)

        vector_results = self.vector_store.retrieve_memory(
            agent_id=agent_id,
            query=query_text,
            limit=limit,
            min_importance=min_importance,
            summary_only=True
        )

        enriched_results = []

        for res in vector_results:
            res_dict = res.dict() if hasattr(res, 'dict') else vars(res)
            
            meta = res_dict.get('metadata', {})
            summary_id = meta.get('summary_id')

            if summary_id:
                sql_data = await self.get_summary_by_id(summary_id)
                if sql_data:
                    res_dict['sql_data'] = sql_data
            
            enriched_results.append(res_dict)

        return enriched_results

    async def search_sql(
        self,
        agent_id: str,
        query_text: str,
        limit: int = 5,
        conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Fallback text search using SQL LIKE."""
        query = """
            SELECT *
            FROM summaries
            WHERE agent_id = ? AND content LIKE ?
        """
        params = [agent_id, f"%{query_text}%"]

        if conversation_id:
            query += " AND conversation_id = ?"
            params.append(conversation_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        return await self.db.fetch_all(query, tuple(params))

    async def get_summary_by_id(self, summary_id: str) -> Optional[Dict[str, Any]]:
        """Fetch full summary details by ID."""
        query = "SELECT * FROM summaries WHERE id = ?"
        return await self.db.fetch_one(query, (summary_id,))

    async def get_summaries_in_range(
        self, 
        conversation_id: str, 
        start_seq: int, 
        end_seq: int
    ) -> List[Dict[str, Any]]:
        """Used to check if a range has already been summarized."""
        query = """
            SELECT * FROM summaries 
            WHERE conversation_id = ? 
            AND message_start_seq >= ? 
            AND message_end_seq <= ?
        """
        return await self.db.fetch_all(query, (conversation_id, start_seq, end_seq))


class HybridSummaryRepository(SummaryRepository):
    """
    Extends SummaryRepository with the write patterns MemoryManager needs:

      - upsert_short_summary(): atomic DELETE + INSERT so there is always exactly
        ONE 'short' summary row per conversation. This is the fix for the
        accumulation bug where get_latest_short_summary returned stale context
        because old rows were never cleaned up.

      - get_latest_short_summary(): canonical name used by MemoryManager (delegates
        to the parent's get_latest_rolling_summary).
    """

    async def upsert_short_summary(
        self,
        conversation_id: str,
        content: str,
        metadata: Dict[str, Any],
        agent_id: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> str:
        """
        Atomically replace the single rolling 'short' summary for a conversation.

        Runs DELETE + INSERT inside one transaction so readers never see a gap
        and concurrent summarization tasks cannot stack duplicate rows.

        The 'short' summary is deliberately NOT vector-indexed (it changes every
        summarization cycle and is only used for the fused system prompt injection).
        """
        summary_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        sql_metadata = json.dumps(metadata) if isinstance(metadata, dict) else metadata

        # Resolve agent_id: accept explicit override or fall back to a stored one.
        # Callers in MemoryManager always have self.agent_id available.
        resolved_agent_id = agent_id or ""

        delete_query = """
            DELETE FROM summaries
            WHERE conversation_id = ? AND summary_type = 'short'
        """
        insert_query = """
            INSERT INTO summaries (
                id, conversation_id, agent_id, summary_type, content,
                importance, message_start_seq, message_end_seq, message_count,
                tags, metadata, created_at
            ) VALUES (?, ?, ?, 'short', ?, 1, 0, 0, 0, '[]', ?, ?)
        """

        # Use the db's transaction context if available; otherwise execute sequentially.
        # If BaseDatabase exposes execute_transaction, prefer it.
        if hasattr(self.db, 'execute_transaction'):
            await self.db.execute_transaction([
                (delete_query, (conversation_id,)),
                (insert_query, (summary_id, conversation_id, resolved_agent_id,
                                content, sql_metadata, created_at)),
            ])
        else:
            # Fallback: two sequential calls. Acceptable because:
            #   1. _summarization_lock in MemoryManager prevents re-entrant writes.
            #   2. The worst case (crash between DELETE and INSERT) self-heals: next
            #      summarization cycle will insert a fresh row.
            await self.db.execute(delete_query, (conversation_id,))
            await self.db.execute(insert_query, (
                summary_id, conversation_id, resolved_agent_id,
                content, sql_metadata, created_at
            ))

        logger.info(f"✅ Short summary upserted for conversation {conversation_id[:8]}… "
                    f"(ID: {summary_id[:8]})")
        return summary_id

    async def get_latest_short_summary(self, conversation_id: str) -> Optional[str]:
        """
        Return the current rolling short summary text for the system prompt.
        Canonical name used throughout MemoryManager; delegates to parent.
        """
        return await self.get_latest_rolling_summary(conversation_id)