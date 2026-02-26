# repositories/summary_repository.py
import json
import uuid
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from database.base import BaseDatabase
from rag.stores.memory import MemoryVectorStore
from rag.schema import MemorySchema

logger = logging.getLogger(__name__)


class HybridSummaryRepository:
    """
    Two-layer summary store:
      - SQLite  : exact text, coverage metadata, rolling 'short' summary.
      - ChromaDB: semantic embeddings for 'long' summaries (RAG recall).
    """

    def __init__(self, db: BaseDatabase, vector_store: Optional[MemoryVectorStore] = None):
        self.db = db
        self.vector_store = vector_store

    # ------------------------------------------------------------------ #
    # Short summary (working memory) — exactly ONE row per conversation   #
    # ------------------------------------------------------------------ #

    async def upsert_short_summary(
        self,
        conversation_id: str,
        agent_id: str,
        content: str,
        message_start_seq: int,
        message_end_seq: int,
        turn_start_id: str,
        turn_end_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        agent_name: Optional[str] = None,
    ) -> str:
        """
        Atomically replace the single rolling short summary.

        Runs DELETE + INSERT in one transaction so:
          - readers never see an empty gap
          - concurrent tasks cannot stack duplicate rows
        """
        summary_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()
        sql_metadata = json.dumps(metadata or {})

        delete_q = """
            DELETE FROM summaries
            WHERE conversation_id = ? AND summary_type = 'short'
        """
        insert_q = """
            INSERT INTO summaries (
                id, conversation_id, agent_id, summary_type, content,
                importance, message_start_seq, message_end_seq, message_count,
                turn_start_id, turn_end_id, tags, metadata, created_at
            ) VALUES (?, ?, ?, 'short', ?, 1, ?, ?, 0, ?, ?, '[]', ?, ?)
        """
        insert_params = (
            summary_id, conversation_id, agent_id, content,
            message_start_seq, message_end_seq,
            turn_start_id, turn_end_id,
            sql_metadata, created_at,
        )

        if hasattr(self.db, "execute_transaction"):
            await self.db.execute_transaction([
                (delete_q, (conversation_id,)),
                (insert_q, insert_params),
            ])
        else:
            # Fallback: sequential.  Safe because _summarization_lock
            # in MemoryManager prevents re-entrancy.
            await self.db.execute(delete_q, (conversation_id,))
            await self.db.execute(insert_q, insert_params)

        logger.info(
            "Short summary upserted for conversation %s (turns %s→%s)",
            conversation_id[:8], turn_start_id[:8], turn_end_id[:8],
        )
        return summary_id

    async def get_short_summary(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Return the full short-summary row (not just content) so callers can
        inspect coverage boundaries and avoid overlapping summarization.
        """
        return await self.db.fetch_one(
            """
            SELECT * FROM summaries
            WHERE conversation_id = ? AND summary_type = 'short'
            LIMIT 1
            """,
            (conversation_id,),
        )

    # ------------------------------------------------------------------ #
    # Long summary (archival memory)                                       #
    # ------------------------------------------------------------------ #

    async def add_long_summary(
        self,
        conversation_id: str,
        agent_id: str,
        content: str,
        importance: int,
        message_start_seq: int,
        message_end_seq: int,
        message_count: int,
        turn_start_id: str,
        turn_end_id: str,
        tags: List[str],
        metadata: Dict[str, Any],
        agent_name: Optional[str] = None,
    ) -> str:
        summary_id = str(uuid.uuid4())
        created_at = datetime.now(timezone.utc).isoformat()

        # Ensure tags and metadata are valid JSON strings
        tags_json = json.dumps(tags) if tags else '[]'
        metadata_json = json.dumps(metadata) if metadata else '{}'
        try : 
            await self.db.execute(
                """
                INSERT INTO summaries (
                    id, conversation_id, agent_id, summary_type, content,
                    importance, message_start_seq, message_end_seq, message_count,
                    turn_start_id, turn_end_id, tags, metadata, created_at
                ) VALUES (?, ?, ?, 'long', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    summary_id, conversation_id, agent_id, content,
                    importance, message_start_seq, message_end_seq, message_count,
                    turn_start_id, turn_end_id,
                    tags_json, metadata_json, created_at,
                ),
            )
        except Exception as e : 
            logger.error("Exception while sotring Long summery to DB, Excepiotn : %s", e)

        # Vector index for semantic recall
        
        try: 
            if self.vector_store:
                safe_meta = {
                    k: json.dumps(v) if isinstance(v, (list, dict)) else v
                    for k, v in {
                        "summary_id": summary_id,
                        "conversation_id": conversation_id,
                        "turn_start_id": turn_start_id,
                        "turn_end_id": turn_end_id,
                        **metadata,
                    }.items()
                }
                self.vector_store.add_memory(MemorySchema(
                    agent_id=agent_id,
                    agent_name=agent_name,
                    content=content,
                    role="summary",
                    summary_type="long",
                    importance=importance,
                    message_count=message_count,
                    tags=tags,
                    metadata=safe_meta,
                    timestamp=created_at,
                ))

            logger.info("Long summary stored: %s", summary_id[:8])
        except Exception as e: 
            logger.error("Exception while sotring Long summery to VectorDB, Excepiotn : %s", e)
        
        return summary_id

    async def search_semantic(
        self,
        agent_id: str,
        query_text: str,
        limit: int = 5,
        min_importance: int = 1,
    ) -> List[Dict[str, Any]]:
        if not self.vector_store:
            return await self._search_sql(agent_id, query_text, limit)

        results = self.vector_store.retrieve_memory(
            agent_id=agent_id,
            query=query_text,
            limit=limit,
            min_importance=min_importance,
            summary_only=True,
        )
        enriched = []
        for res in results:
            d = res.dict() if hasattr(res, "dict") else vars(res)
            sid = d.get("metadata", {}).get("summary_id")
            if sid:
                sql_row = await self.db.fetch_one(
                    "SELECT * FROM summaries WHERE id = ?", (sid,)
                )
                if sql_row:
                    d["sql_data"] = dict(sql_row)
            enriched.append(d)
        return enriched

    async def _search_sql(
        self,
        agent_id: str,
        query_text: str,
        limit: int,
        conversation_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        q = "SELECT * FROM summaries WHERE agent_id = ? AND content LIKE ?"
        params: list = [agent_id, f"%{query_text}%"]
        if conversation_id:
            q += " AND conversation_id = ?"
            params.append(conversation_id)
        q += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)
        return await self.db.fetch_all(q, tuple(params))