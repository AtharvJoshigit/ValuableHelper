# src/rag/stores/memory.py (Updated)
from typing import List, Dict, Any, Optional
import json
from rag.stores.base import BaseVectorStore
from rag.schema import MemorySchema, VectorDocument, SearchResult
from rag.config import settings
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
        # Flatten metadata for ChromaDB (no nested dicts/lists allowed)
        safe_tags = ",".join(memory.tags) if memory.tags else ""
        
        # Serialize any complex types in metadata
        safe_extra_metadata = {}
        for k, v in memory.metadata.items():
            if isinstance(v, (dict, list)):
                safe_extra_metadata[k] = json.dumps(v)
            else:
                safe_extra_metadata[k] = v

        enriched_metadata = {
            "agent_id": memory.agent_id,
            "agent_name": memory.agent_name or "unknown",
            "role": memory.role,
            "summary_type": memory.summary_type or "unknown",
            "importance": memory.importance,
            "timestamp": memory.timestamp.isoformat(),
            "message_count": memory.message_count or 0,
            "tags": safe_tags, # Stored as comma-separated string
            **safe_extra_metadata
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
        """
        # Build filter for ChromaDB
        where_clause = {
            "$and": [
                {"agent_id": {"$eq": agent_id}}
            ]
        }
        
        if summary_only:
            where_clause["$and"].append({"role": {"$eq": "summary"}})
        
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
                    # Reconstruct tags from string
                    tags_str = r.metadata.get("tags", "")
                    tags_list = tags_str.split(",") if tags_str else []
                    
                    filtered.append({
                        "content": r.content,
                        "importance": importance,
                        "timestamp": r.metadata.get("timestamp"),
                        "tags": tags_list,
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
        try:
            # Chroma doesn't support "contains" for strings easily, so we rely on semantic search + post-filtering
            # Or exact match if we stored tags individually, but we stored as CSV string.
            # Semantic search is better here.
            
            results: List[SearchResult] = self.search(
                query=" ".join(tags),  # Use tags as query context
                n_results=limit * 3,
                where={"agent_id": agent_id}
            )
            
            filtered = []
            for r in results:
                tags_str = r.metadata.get("tags", "")
                mem_tags = tags_str.split(",") if tags_str else []
                
                # Check if ANY requested tag is in the memory's tags
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
