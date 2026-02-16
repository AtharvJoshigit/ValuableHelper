# engine/registry/library/memory_retrieval_tool.py (CORRECTED)
from typing import Any, List, Dict
from engine.core.memory_manager import MemoryManager
from pydantic import Field
from engine.registry.base_tool import BaseTool
import logging
import asyncio

logger = logging.getLogger(__name__)

class MemoryRetrievalTool(BaseTool):
    """
    Search long-term conversation memory using intelligent query routing.
    
    Automatically selects optimal search method:
    - Semantic search for conceptual queries
    - Temporal search for time-based queries  
    - Importance filtering for critical information
    - Exact matching for specific phrases
    """
    
    name: str = "search_memory"
    description: str = (
        "Search your long-term conversation memory. Use this when you need to recall "
        "previous discussions, user preferences, or important context from past conversations.\n\n"
        "Query types:\n"
        "- Conceptual: 'what did we discuss about deadlines?'\n"
        "- Temporal: 'conversations from last week'\n"
        "- Importance: 'most important discussions'\n"
        "- Exact: 'when did user mention feature X?'"
    )
    capabilities: List[str] = ["semantic_search", "temporal_search", "exact_search"]
    tags: List[str] = ["memory", "retrieval", "context", "history"]
    
    query: str = Field(
        "",  # Required field
        description="What to search for in memory. Be specific about what you're looking for."
    )
    limit: int = Field(
        default=5, 
        ge=1, 
        le=10, 
        description="Maximum number of memory results to return (1-10)"
    )
    min_importance: int = Field(
        default=1, 
        ge=1, 
        le=10, 
        description="Minimum importance level (1-10). Use 7+ for critical information only."
    )
    
    def execute(self, **kwargs) -> Any:
        """Execute intelligent memory search with proper async handling."""
        try:
            # Get agent_id from kwargs
            agent_id = kwargs.get("agent_id")
            if not agent_id:
                print({"error": "Agent ID not provided"})
            
            # Get agent from manager
            from app.app_context import get_app_context
            context = get_app_context()
            agent = context.agent_manager.get_agent(agent_id)
            
            if not agent:
                return {"error": f"Agent '{agent_id}' not found"}
            
            # Check if agent has database-backed memory
            if not hasattr(agent, 'memory'):
                return {"error": "Agent has no memory system"}
            
            memory = agent.memory
            
            # Check memory type - MemoryManager vs old Memory
            from engine.core.memory_manager import MemoryManager
            
            if not isinstance(memory, MemoryManager):
                return {
                    "error": "Memory search requires database-backed memory. "
                    "This agent uses in-memory storage only."
                }
            
            # Check if memory is initialized
            if not memory.conversation_id:
                return {
                    "info": "No conversation history yet. Memory search will be "
                    "available after some conversation has occurred."
                }
            
            # Perform async memory search
            results = self._search_memory_sync(
                memory=memory,
                agent_id=agent_id,
                query=self.query,
                limit=self.limit,
                min_importance=self.min_importance
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Memory search failed: {e}", exc_info=True)
            return {"error": f"Memory search failed: {str(e)}"}
    
    def _search_memory_sync(
        self,
        memory: MemoryManager,
        agent_id: str,
        query: str,
        limit: int,
        min_importance: int
    ) -> str:
        """Synchronous wrapper for async memory search."""
        try:
            # Try to get running loop
            try:
                loop = asyncio.get_running_loop()
                # We're in an async context, need to create task
                # This is tricky - tools run sync but memory is async
                # We need to run in a new thread or use run_until_complete carefully
                
                # Create new loop in thread pool for isolation
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self._async_search(memory, query, limit, min_importance)
                    )
                    results = future.result(timeout=30)
                    return results
                    
            except RuntimeError:
                # No running loop - we can use asyncio.run directly
                results = asyncio.run(
                    self._async_search(memory, query, limit, min_importance)
                )
                return results
                
        except Exception as e:
            logger.error(f"Sync memory search wrapper failed: {e}")
            return f"Memory search error: {str(e)}"
    
    async def _async_search(
        self,
        memory: 'MemoryManager',
        query: str,
        limit: int,
        min_importance: int
    ) -> str:
        """Perform the actual async memory search."""
        from engine.core.memory_query_router import MemoryQueryRouter
        
        # Ensure memory is initialized
        if not memory.conversation_id:
            await memory.initialize()
        
        # Use query router for intelligent search
        router = MemoryQueryRouter()
        results = await router.route_query(
            query=query,
            agent_id=memory.agent_id,
            repository=memory.summary_repo,
            limit=limit
        )
        
        # Filter by importance
        filtered = [r for r in results if r.get('importance', 0) >= min_importance]
        
        if not filtered:
            return (
                f"No memories found matching '{query}' with importance >= {min_importance}. "
                f"Try lowering min_importance or using a different search query."
            )
        
        # Format results clearly
        formatted = [
            f"Found {len(filtered)} relevant memor{'y' if len(filtered) == 1 else 'ies'}:\n"
        ]
        
        for i, mem in enumerate(filtered, 1):
            importance = mem.get('importance', 5)
            timestamp = mem.get('created_at', 'unknown')
            content = mem.get('content', '')
            search_method = mem.get('search_method', 'unknown')
            
            # Truncate long content
            if len(content) > 300:
                content = content[:297] + "..."
            
            # Show relevance score if from semantic search
            score_info = ""
            if 'score' in mem and search_method == 'semantic':
                relevance = (1 - mem['score']) * 100
                score_info = f" | Relevance: {relevance:.0f}%"
            
            formatted.append(
                f"\n{'='*50}\n"
                f"Memory {i} (Importance: {importance}/10{score_info})\n"
                f"Date: {timestamp}\n"
                f"Search method: {search_method}\n"
                f"\n{content}\n"
            )
        
        return "".join(formatted)