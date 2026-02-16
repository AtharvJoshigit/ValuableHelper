# infrastructure/repositories/summary_repository.py (Updated)
from datetime import datetime, timezone
import json
import uuid
import logging
from typing import List, Optional, Dict, Any
from database.base import BaseDatabase
from rag.stores.memory import MemoryVectorStore
from src.rag.schema import MemorySchema

logger = logging.getLogger(__name__)

class SummaryRepository:
    """Base SQL repository for summary CRUD operations."""
    
    def __init__(self, db: BaseDatabase):
        self.db = db
    
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
        metadata: Dict[str, Any]
    ) -> str:
        """Store a summary in SQL only."""
        summary_id = str(uuid.uuid4())
        
        query = """
            INSERT INTO summaries (
                id, conversation_id, agent_id, summary_type, content,
                importance, message_start_seq, message_end_seq, message_count,
                tags, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        params = (
            summary_id,
            conversation_id,
            agent_id,
            summary_type,
            content,
            importance,
            message_start_seq,
            message_end_seq,
            message_count,
            json.dumps(tags),
            json.dumps(metadata)
        )
        
        await self.db.execute(query, params)
        return summary_id
    
    async def get_latest_short_summary(
        self,
        conversation_id: str
    ) -> Optional[str]:
        """Get the most recent short summary."""
        query = """
            SELECT content
            FROM summaries
            WHERE conversation_id = ? AND summary_type = 'short'
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = await self.db.fetch_one(query, (conversation_id,))
        return row['content'] if row else None
    
    async def get_all_summaries(
        self,
        conversation_id: str,
        summary_type: Optional[str] = None,
        min_importance: int = 1
    ) -> List[Dict[str, Any]]:
        """Get all summaries for a conversation."""
        query = """
            SELECT id, summary_type, content, importance, message_count,
                   tags, created_at, metadata
            FROM summaries
            WHERE conversation_id = ? AND importance >= ?
        """
        params = [conversation_id, min_importance]
        
        if summary_type:
            query += " AND summary_type = ?"
            params.append(summary_type)
        
        query += " ORDER BY created_at DESC"
        
        return await self.db.fetch_all(query, tuple(params))
    
    async def get_summary_by_id(self, summary_id: str) -> Optional[Dict[str, Any]]:
        """Get full summary details by ID."""
        query = "SELECT * FROM summaries WHERE id = ?"
        return await self.db.fetch_one(query, (summary_id,))

class HybridSummaryRepository:
    """
    Hybrid storage: SQLite for metadata + ChromaDB for semantic search.
    Best of both worlds.
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
        Store summary in BOTH SQLite and ChromaDB.
        SQLite: Fast metadata queries, temporal access
        ChromaDB: Semantic search
        """
        summary_id = str(uuid.uuid4())
        
        # 1. Store in SQLite (metadata + full content)
        sql_query = """
            INSERT INTO summaries (
                id, conversation_id, agent_id, summary_type, content,
                importance, message_start_seq, message_end_seq, message_count,
                tags, metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        await self.db.execute(
            sql_query,
            (
                summary_id,
                conversation_id,
                agent_id,
                summary_type,
                content,
                importance,
                message_start_seq,
                message_end_seq,
                message_count,
                json.dumps(tags),
                json.dumps(metadata)
            )
        )
        
        # 2. Store in ChromaDB for semantic search (only long summaries)
        if summary_type == "long" and self.vector_store:
            memory_schema = MemorySchema(
                agent_id=agent_id,
                agent_name=agent_name,
                content=content,
                role="summary",
                summary_type=summary_type,
                importance=importance,
                message_count=message_count,
                tags=json.dumps(tags),
                timestamp=metadata.get("summarized_at") or datetime.now(timezone.utc).isoformat()
            )
            

            safe_metadata = {
                k: json.dumps(v) if isinstance(v, list) else v
                for k, v in metadata.items()
            }

            # Add additional metadata for linking
            memory_schema.metadata = {
                **safe_metadata,
                "summary_id": summary_id,
                "conversation_id": conversation_id,
                "message_start_seq": message_start_seq,
                "message_end_seq": message_end_seq
            }
            
            self.vector_store.add_memory(memory_schema)
        
        logger.info(
            f"✅ Summary stored: SQLite + {'ChromaDB' if summary_type == 'long' else 'SQLite only'} "
            f"(id={summary_id[:8]}, type={summary_type})"
        )
        
        return summary_id
    
    async def search_semantic(
        self,
        agent_id: str,
        query: str,
        limit: int = 5,
        min_importance: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Semantic search using ChromaDB embeddings.
        Use this when user asks conceptual questions.
        """
        if not self.vector_store:
            logger.warning("Vector store not available, falling back to SQL search")
            return await self.search_sql(agent_id, query, limit)
        
        # Semantic search via embeddings
        vector_results = self.vector_store.retrieve_memory(
            agent_id=agent_id,
            query=query,
            limit=limit,
            min_importance=min_importance,
            summary_only=True
        )
        
        # Enrich with SQL metadata if needed
        enriched = []
        for result in vector_results:
            summary_id = result.get("metadata", {}).get("summary_id")
            if summary_id:
                # Get full metadata from SQL
                sql_data = await self.get_summary_by_id(summary_id)
                if sql_data:
                    enriched.append({
                        **result,
                        "sql_metadata": sql_data
                    })
                else:
                    enriched.append(result)
            else:
                enriched.append(result)
        
        return enriched
    
    async def search_sql(
        self,
        agent_id: str,
        query: str,
        limit: int = 5,
        conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Traditional SQL text search.
        Use this for exact matches or when vector store unavailable.
        """
        sql_query = """
            SELECT id, conversation_id, summary_type, content, importance,
                   message_count, tags, created_at, metadata
            FROM summaries
            WHERE agent_id = ? AND content LIKE ?
        """
        params = [agent_id, f"%{query}%"]
        
        if conversation_id:
            sql_query += " AND conversation_id = ?"
            params.append(conversation_id)
        
        sql_query += " ORDER BY importance DESC, created_at DESC LIMIT ?"
        params.append(limit)
        
        return await self.db.fetch_all(sql_query, tuple(params))
    
    async def get_by_timerange(
        self,
        agent_id: str,
        start_date: str,
        end_date: str,
        min_importance: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Temporal queries are better in SQL.
        Example: "Show me summaries from last month"
        """
        query = """
            SELECT id, conversation_id, summary_type, content, importance,
                   message_count, tags, created_at, metadata
            FROM summaries
            WHERE agent_id = ?
              AND created_at BETWEEN ? AND ?
              AND importance >= ?
            ORDER BY created_at DESC
        """
        return await self.db.fetch_all(
            query,
            (agent_id, start_date, end_date, min_importance)
        )
    
    async def get_by_importance(
        self,
        agent_id: str,
        min_importance: int = 7,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Get most important summaries.
        SQL is perfect for this structured query.
        """
        query = """
            SELECT id, conversation_id, summary_type, content, importance,
                   message_count, tags, created_at, metadata
            FROM summaries
            WHERE agent_id = ? AND importance >= ?
            ORDER BY importance DESC, created_at DESC
            LIMIT ?
        """
        return await self.db.fetch_all(query, (agent_id, min_importance, limit))
    
    async def get_latest_short_summary(
        self,
        conversation_id: str
    ) -> Optional[str]:
        """Fast exact lookup from SQL."""
        query = """
            SELECT content
            FROM summaries
            WHERE conversation_id = ? AND summary_type = 'short'
            ORDER BY created_at DESC
            LIMIT 1
        """
        row = await self.db.fetch_one(query, (conversation_id,))
        return row['content'] if row else None
    
    async def get_summary_by_id(self, summary_id: str) -> Optional[Dict[str, Any]]:
        """Get full summary details by ID."""
        query = """
            SELECT * FROM summaries WHERE id = ?
        """
        return await self.db.fetch_one(query, (summary_id,))