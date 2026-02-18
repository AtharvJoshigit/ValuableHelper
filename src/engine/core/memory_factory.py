# file: engine/core/memory_factory.py

from typing import Optional, Any
from database.base import BaseDatabase
from engine.core.memory_manager import MemoryManager, InMemoryMessageRepository
from engine.core.agent_instance_manager import AgentConfig
import logging

logger = logging.getLogger(__name__)


def create_memory_manager(
    agent_id: str,
    config: AgentConfig,
    db: BaseDatabase,
    provider: Optional[Any] = None
) -> MemoryManager:
    """
    Factory to create MemoryManager from AgentConfig.
    
    Args:
        agent_id: Unique agent identifier
        config: Agent configuration
        db: Database instance
        provider: Optional LLM provider for summarization
        
    Returns:
        Configured MemoryManager instance
    """
    try:
        from repositories.message_repository import MessageRepository
        message_repo = MessageRepository(db)
        logger.info(f"Using MessageRepository for agent '{agent_id}'")
    except (ImportError, Exception) as e:
        logger.warning(f"DB repository unavailable ({e}), falling back to in-memory")
        message_repo = InMemoryMessageRepository()
    
    return MemoryManager(
        db=db,
        agent_id=agent_id,
        agent_name=config.agent_name,
        recent_k=config.memory_recent_k,
        summarization_threshold=config.memory_summarization_threshold,
        enable_summarization=config.enable_memory_summarization,
        auto_summarize=True,
        message_repo=message_repo,
        provider=provider
    )