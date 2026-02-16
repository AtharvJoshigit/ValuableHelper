# src/rag/stores/memory_store.py (Updated)
from typing import List, Dict, Any, Optional
from src.rag.stores.base import BaseVectorStore
from src.rag.schema import MemorySchema, VectorDocument, SearchResult
from src.rag.config import settings
import logging

logger = logging.getLogger(__name__)

class MemoryVectorStore(BaseVectorStore):
    """Enhanced memory store with rich filtering and retrieval for semantic search."""
    
    def __init__(self):
        super().__init__(settings.COLLECTION_MEMORY)
        
    def add_memory(self, memory: MemorySchema):
        """
        Add an episodic memory or summary to the vector store.
        Typically used for long summaries that benefit from semantic search.
        """
        # Enrich metadata
        enriched_metadata = {
            "agent_id": memory.agent_id,
            "agent_name": memory.agent_name or "unknown",
            "role": memory.role,
            "summary_type": memory.summary_type,
            "importance": memory.importance,
            "timestamp": memory.timestamp.isoformat(),
            "message_count": memory.message_count,
            "tags": memory.tags,
            **memory.metadata  # Include any additional metadata
        }
        
        doc = VectorDocument(
            content=memory.content,
            metadata=enriched_metadata
        )
        
        self.add_documents([doc])
        logger.info(f"✅ Added memory to vector store: agent={memory.agent_id}, type={memory.summary_type}")
        
    def retrieve_memory(
        self, 
        agent_id: str, 
        query: str, 
        limit: int = 5,
        min_importance: int = 1,
        summary_only: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Retrieve memories for an agent with semantic search and filtering.
        
        Args:
            agent_id: Agent identifier
            query: Semantic search query
            limit: Max results
            min_importance: Minimum importance score (1-10)
            summary_only: Only return summary entries (not individual messages)
        
        Returns:
            List of memory dictionaries with content and metadata
        """
        # Build filter for ChromaDB
        where_clause = {"agent_id": agent_id}
        
        if summary_only:
            where_clause["role"] = "summary"
        
        try:
            # Semantic search with filters
            results: List[SearchResult] = self.search(
                query, 
                n_results=limit * 2,  # Over-fetch for post-filtering
                where=where_clause
            )
            
            # Post-filter by importance and re-rank
            filtered = []
            for r in results:
                importance = r.metadata.get("importance", 5)
                if importance >= min_importance:
                    filtered.append({
                        "content": r.content,
                        "importance": importance,
                        "timestamp": r.metadata.get("timestamp"),
                        "tags": r.metadata.get("tags", []),
                        "score": r.score,
                        "message_count": r.metadata.get("message_count"),
                        "metadata": r.metadata
                    })
            
            # Sort by combined score (importance * relevance)
            filtered.sort(
                key=lambda x: x["importance"] * (1 - x["score"]), 
                reverse=True
            )
            
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"Vector search failed: {e}")
            return []
    
    def retrieve_by_tags(
        self,
        agent_id: str,
        tags: List[str],
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Retrieve memories by specific tags."""
        # This requires custom filtering - implementation depends on your vector DB
        # For ChromaDB, you might need to do post-filtering
        try:
            results: List[SearchResult] = self.search(
                query=" ".join(tags),  # Use tags as query
                n_results=limit * 2,
                where={"agent_id": agent_id}
            )
            
            filtered = []
            for r in results:
                mem_tags = r.metadata.get("tags", [])
                if any(tag in mem_tags for tag in tags):
                    filtered.append({
                        "content": r.content,
                        "importance": r.metadata.get("importance", 5),
                        "timestamp": r.metadata.get("timestamp"),
                        "tags": mem_tags,
                        "score": r.score,
                        "metadata": r.metadata
                    })
            
            return filtered[:limit]
            
        except Exception as e:
            logger.error(f"Tag-based retrieval failed: {e}")
            return []