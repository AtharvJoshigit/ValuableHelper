# engine/core/memory_manager.py
import logging
import asyncio
from typing import List, Optional, Dict, Any
from engine.core.summerizer import MemorySummarizer
from engine.core.types import Message, Role
from database.base import BaseDatabase
from rag.stores.memory import MemoryVectorStore
from repositories.message_repository import MessageRepository
from repositories.conversation_repository import ConversationRepository
from repositories.summary_repository import HybridSummaryRepository

logger = logging.getLogger(__name__)

class MemoryManager:
    """
    Optimized memory manager with database backend.
    Minimizes RAM usage by keeping only recent K messages in memory.
    """
    
    def __init__(
        self,
        db: BaseDatabase,
        agent_id: str,
        agent_name: Optional[str] = None,
        recent_k: int = 10,
        summarization_threshold: int = 20,
        enable_summarization: bool = False,
        auto_summarize: bool = True,
        session_timeout_hours: int = 24
    ):
        self.db = db
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.recent_k = recent_k
        self.summarization_threshold = summarization_threshold
        self.enable_summarization = enable_summarization
        self.auto_summarize = auto_summarize
        self.session_timeout_hours = session_timeout_hours
        
        # Repositories
        self.message_repo = MessageRepository(db)
        self.summary_repo = HybridSummaryRepository(
            db=db,
            vector_store=MemoryVectorStore() if enable_summarization else None
        )
        self.conversation_repo = ConversationRepository(db)
        
        # State
        self.conversation_id: Optional[str] = None
        self._sequence_counter: int = 0
        self._summarization_lock = asyncio.Lock()
        
        self._is_summarizing = False # safe guard for next tasks to control 
        
        # Lightweight cache (only recent K)
        self._cache: List[Message] = []
        self._cache_dirty = True
        
        # Summarization
        self._summarizer: Optional[MemorySummarizer] = None
        if enable_summarization:
            self._summarizer = MemorySummarizer(agent_id=agent_id)
        
        self.summary_repo = HybridSummaryRepository(
            db=db,
            vector_store=MemoryVectorStore() if enable_summarization else None
        )
    
    async def initialize(self):
        """
        Initialize conversation session with resumption support.
        Will resume recent conversation if exists, otherwise create new.
        """
        self.conversation_id = await self.conversation_repo.get_or_create_active_conversation(
            agent_id=self.agent_id,
            agent_name=self.agent_name,
            session_timeout_hours=self.session_timeout_hours
        )
        
        # Get current sequence number
        count = await self.message_repo.get_message_count(self.conversation_id)
        self._sequence_counter = count
        
        # Get conversation summary
        summary = await self.conversation_repo.get_conversation_summary(
            self.conversation_id
        )
        
        logger.info(
            f"✅ Memory initialized for agent {self.agent_id}\n"
            f"  Conversation: {self.conversation_id}\n"
            f"  Messages: {count} ({summary.get('summarized_count', 0)} summarized)\n"
            f"  Created: {summary.get('created_at', 'unknown')}\n"
            f"  Last active: {summary.get('updated_at', 'unknown')}"
        )
    
    async def add_message(self, message: Message):
        """
        Add message to database (not RAM).
        This is the PRIMARY operation - everything goes to DB first.
        """
        if not self.conversation_id:
            await self.initialize()
        
        # Increment sequence
        self._sequence_counter += 1
        
        # Store in database immediately
        await self.message_repo.add_message(
            conversation_id=self.conversation_id,
            agent_id=self.agent_id,
            message=message,
            sequence_number=self._sequence_counter
        )
        
        # Invalidate cache
        self._cache_dirty = True
        
        # Update conversation timestamp
        await self.conversation_repo.update_conversation_timestamp(self.conversation_id)
        
        # Check if we should trigger summarization
        if self.enable_summarization and self.auto_summarize:
            await self._check_and_summarize()
    
    async def start_fresh_conversation(self):
        """
        Explicitly start a new conversation (ignore session timeout).
        Use this when user says "start over" or "new conversation".
        """
        # End all active conversations
        await self.conversation_repo.end_all_conversations(self.agent_id)
        
        # Create new conversation
        self.conversation_id = await self.conversation_repo.create_conversation(
            agent_id=self.agent_id,
            agent_name=self.agent_name
        )
        
        self._sequence_counter = 0
        self._cache = []
        self._cache_dirty = True
        
        logger.info(f"✅ Started fresh conversation: {self.conversation_id}")

    async def add_user_message(self, content: str):
        """Convenience method to add user message."""
        await self.add_message(Message(role=Role.USER, content=content))
    
    async def get_history(self) -> List[Message]:
        """
        Get optimized conversation history for LLM.
        Structure: [System] + [Latest Summary (if exists)] + [Recent K]
        
        This is LAZY LOADED from DB only when needed.
        """
        if not self.conversation_id:
            await self.initialize()
        
        history = []
        
        # 1. Get system message (if exists)
        system_msg = await self.message_repo.get_system_message(self.conversation_id)
        if system_msg:
            history.append(system_msg)
        
        # 2. Get latest short summary (if exists and summarization enabled)
        if self.enable_summarization:
            short_summary = await self.summary_repo.get_latest_short_summary(
                self.conversation_id
            )
            if short_summary:
                history.append(Message(
                    role=Role.SYSTEM,
                    content=f"""## Previous Conversation Summary
{short_summary}

The following are the most recent messages:"""
                ))
        
        # 3. Get recent K messages from DB (use cache if valid)
        if self._cache_dirty or not self._cache:
            self._cache = await self.message_repo.get_recent_messages(
                conversation_id=self.conversation_id,
                limit=self.recent_k,
                exclude_system=True
            )
            self._cache_dirty = False
        
        history.extend(self._cache)
        
        return history
    
    async def get_full_history(self) -> List[Message]:
        """Get ALL messages from database (for debugging/export)."""
        if not self.conversation_id:
            return []
        
        # This is expensive - only use for debugging
        query = """
            SELECT role, content, tool_calls, tool_results
            FROM messages
            WHERE conversation_id = ?
            ORDER BY sequence_number ASC
        """
        rows = await self.db.fetch_all(query, (self.conversation_id,))
        return [self.message_repo._row_to_message(row) for row in rows]
    
    async def _check_and_summarize(self):
        """
        Smart summarization check.
        Only summarizes if we have enough unsummarized messages.
        """
        if self._is_summarizing: # Guard against concurrent tasks
            return
        
        unsummarized_count = await self.message_repo.get_message_count(
            conversation_id=self.conversation_id,
            unsummarized_only=True
        )
        
        print(f"Unsummarized count: {unsummarized_count}, Summerization Threshold : {self.summarization_threshold}")
        # Need enough messages to make summarization worthwhile
        if unsummarized_count < self.summarization_threshold:
            return
        
        # Trigger async summarization (non-blocking)
        asyncio.create_task(self._perform_summarization())
    
    async def _perform_summarization(self):
        """
        Perform actual summarization.
        Runs asynchronously to not block message addition.
        """
        async with self._summarization_lock:
            try:
                self._is_summarizing = True
                if not self.conversation_id or not self._summarizer:
                    return
                
                # Get messages to summarize (excluding recent K)
                messages, start_seq, end_seq = await self.message_repo.get_unsummarized_messages(
                    conversation_id=self.conversation_id,
                    skip_recent_k=self.recent_k
                )
                
                if not messages:
                    return
                
                logger.info(
                    f"📝 Summarizing {len(messages)} messages "
                    f"(seq {start_seq}-{end_seq}) for agent {self.agent_id}"
                )
                
                # Generate summaries
                summaries = await self._summarizer.summarize_conversations(
                    messages=messages,
                    agent_name=self.agent_name
                )
                
                # Use transaction for atomicity
                async with self.db.transaction():
                    # Store short summary
                    if summaries["short"]:
                        await self.summary_repo.add_summary(
                            conversation_id=self.conversation_id,
                            agent_id=self.agent_id,
                            summary_type="short",
                            content=summaries["short"],
                            importance=summaries["importance"],
                            message_start_seq=start_seq,
                            message_end_seq=end_seq,
                            message_count=len(messages),
                            tags=[],
                            metadata=summaries.get("metadata", {})
                        )
                    
                    # Store long summary
                    if summaries["long"]:
                        await self.summary_repo.add_summary(
                            conversation_id=self.conversation_id,
                            agent_id=self.agent_id,
                            summary_type="long",
                            content=summaries["long"],
                            importance=summaries["importance"],
                            message_start_seq=start_seq,
                            message_end_seq=end_seq,
                            message_count=len(messages),
                            tags=summaries["metadata"].get("key_topics", []),
                            metadata=summaries.get("metadata", {})
                        )
                    
                    # Mark messages as summarized
                    await self.message_repo.mark_as_summarized(
                        conversation_id=self.conversation_id,
                        start_seq=start_seq,
                        end_seq=end_seq
                    )
                
                logger.info(
                    f"✅ Summarization complete for agent {self.agent_id}: "
                    f"{len(messages)} messages, importance={summaries['importance']}"
                )
                
            except Exception as e:
                logger.error(f"❌ Summarization failed for agent {self.agent_id}: {e}", exc_info=True)
    
            finally:
                self._is_summarizing = False
                
    async def search_summaries(
        self,
        query: str,
        limit: int = 5,
        min_importance: int = 1
    ) -> List[Dict[str, Any]]:
        """
        Search historical summaries.
        Note: This searches DB summaries, not vector embeddings.
        """
        if not self.conversation_id:
            return []
        
        summaries = await self.summary_repo.get_all_summaries(
            conversation_id=self.conversation_id,
            summary_type="long",
            min_importance=min_importance
        )
        
        # Simple text matching (can be enhanced with vector search)
        query_lower = query.lower()
        results = []
        
        for summary in summaries:
            if query_lower in summary['content'].lower():
                results.append(summary)
                if len(results) >= limit:
                    break
        
        return results
    
    async def get_statistics(self) -> Dict[str, Any]:
        """Get memory statistics."""
        if not self.conversation_id:
            return {}
        
        total_messages = await self.message_repo.get_message_count(self.conversation_id)
        unsummarized = await self.message_repo.get_message_count(
            self.conversation_id,
            unsummarized_only=True
        )
        summaries = await self.summary_repo.get_all_summaries(self.conversation_id)
        
        return {
            "agent_id": self.agent_id,
            "conversation_id": self.conversation_id,
            "total_messages": total_messages,
            "unsummarized_messages": unsummarized,
            "total_summaries": len(summaries),
            "cache_size": len(self._cache),
            "recent_k": self.recent_k
        }
    
    async def search_memory(
        self, 
        query: str, 
        limit: int = 5,
        min_importance: int = 1
        
    ) -> List[Dict[str, Any]]:
        """Smart search using query router."""
        from engine.core.memory_query_router import MemoryQueryRouter
        
        router = MemoryQueryRouter()
        return await router.route_query(
            query=query,
            agent_id=self.agent_id,
            repository=self.summary_repo,
            limit=limit
        )

    async def clear(self):
        """Clear conversation (mark as inactive and start fresh)."""
        if self.conversation_id:
            await self.conversation_repo.deactivate_conversation(self.conversation_id)
        
        self.conversation_id = None
        self._sequence_counter = 0
        self._cache = []
        self._cache_dirty = True