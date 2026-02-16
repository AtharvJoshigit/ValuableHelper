# engine/core/memory_query_router.py
import re
from typing import List, Dict, Any, Optional
from enum import Enum

from repositories.summary_repository import HybridSummaryRepository

class QueryType(Enum):
    SEMANTIC = "semantic"  # Conceptual: "tell me about deadlines"
    TEMPORAL = "temporal"  # Time-based: "last week", "in March"
    EXACT = "exact"        # Specific: "conversation about feature X"
    IMPORTANCE = "importance"  # "most important discussions"

class MemoryQueryRouter:
    """
    Intelligent router that decides: SQLite vs ChromaDB vs Both.
    Analyzes query intent and routes to optimal storage.
    """
    
    TEMPORAL_KEYWORDS = [
        'yesterday', 'today', 'last week', 'last month', 'recently',
        'this week', 'this month', 'january', 'february', 'march', 'april',
        'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'
    ]
    
    IMPORTANCE_KEYWORDS = [
        'important', 'critical', 'urgent', 'priority', 'key', 'major', 'significant'
    ]
    
    EXACT_KEYWORDS = [
        'specific', 'exactly', 'particular', 'precise'
    ]
    
    def classify_query(self, query: str) -> QueryType:
        """Classify query type to choose optimal storage."""
        query_lower = query.lower()
        
        # Check for temporal queries
        if any(keyword in query_lower for keyword in self.TEMPORAL_KEYWORDS):
            return QueryType.TEMPORAL
        
        # Check for importance queries
        if any(keyword in query_lower for keyword in self.IMPORTANCE_KEYWORDS):
            return QueryType.IMPORTANCE
        
        # Check for exact match queries
        if any(keyword in query_lower for keyword in self.EXACT_KEYWORDS):
            return QueryType.EXACT
        
        # Default to semantic search for conceptual queries
        return QueryType.SEMANTIC
    
    async def route_query(
        self,
        query: str,
        agent_id: str,
        repository: HybridSummaryRepository,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Route query to appropriate storage backend(s)."""
        query_type = self.classify_query(query)
        
        if query_type == QueryType.SEMANTIC:
            # Use ChromaDB for semantic understanding
            return await repository.search_semantic(
                agent_id=agent_id,
                query=query,
                limit=limit
            )
        
        elif query_type == QueryType.TEMPORAL:
            # Use SQL for time-based queries
            # Parse dates from query (simplified example)
            dates = self._extract_dates(query)
            if dates:
                return await repository.get_by_timerange(
                    agent_id=agent_id,
                    start_date=dates['start'],
                    end_date=dates['end']
                )
            # Fallback to semantic if date parsing fails
            return await repository.search_semantic(agent_id, query, limit)
        
        elif query_type == QueryType.IMPORTANCE:
            # Use SQL for structured importance queries
            return await repository.get_by_importance(
                agent_id=agent_id,
                min_importance=7,
                limit=limit
            )
        
        elif query_type == QueryType.EXACT:
            # Use SQL text search for exact matching
            return await repository.search_sql(
                agent_id=agent_id,
                query=query,
                limit=limit
            )
        
        # Default fallback
        return await repository.search_semantic(agent_id, query, limit)
    
    def _extract_dates(self, query: str) -> Optional[Dict[str, str]]:
        """Extract date range from query (simplified)."""
        from datetime import datetime, timedelta
        
        query_lower = query.lower()
        now = datetime.now()
        
        if 'last week' in query_lower:
            return {
                'start': (now - timedelta(days=7)).isoformat(),
                'end': now.isoformat()
            }
        elif 'last month' in query_lower:
            return {
                'start': (now - timedelta(days=30)).isoformat(),
                'end': now.isoformat()
            }
        # Add more date parsing logic as needed
        
        return None