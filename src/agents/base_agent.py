# src/agents/base_agent.py (UPDATED)

from pathlib import Path
from typing import Optional, Set, Union, List, AsyncIterator
import logging
import asyncio

from engine.core.agent import Agent
from engine.core.agent_factory import create_agent, get_global_database
from engine.registry.tool_registry import ToolRegistry
from engine.core.agent_instance_manager import AgentConfig, get_agent_manager
from engine.core.types import StreamChunk
from services.model_preferences import get_model_preferences

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for creating specialized agent types.
    Updated to support database-backed memory with async initialization.
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        
        # Default values
        self.model_id = self.config.get("model_id", "gemini-2.5-pro")
        self.provider_name = self.config.get("provider", "google")
        self.max_steps = self.config.get("max_steps", 20)
        self.temperature = self.config.get("temperature", 0.7)
        self.top_p = self.config.get("top_p", None)
        self.top_k = self.config.get("top_k", None)
        self.max_tokens = self.config.get("max_tokens", None)
        self.sensitive_tool_names: Set[str] = self.config.get("sensitive_tool_names", set())
        self.additional_params = self.config.get("additional_params", {})
        
        # Memory settings
        self.enable_memory = self.config.get("enable_memory_summarization", False)
        self.agent_name = self.config.get("agent_name", None)
        
        # The active engine instance
        self._engine_agent: Optional[Agent] = None
        self._initialization_pending = False

    def _get_project_root(self) -> Path:
        """Dynamically finds the project root."""
        return Path(__file__).resolve().parents[2]

    def _load_prompt(self, filenames: Union[str, List[str]]) -> str:
        """Loads a markdown prompt from the me/ directory."""
        if isinstance(filenames, str):
            filenames = [filenames]

        try:
            prompt = ""
            for filename in filenames:
                prompt_path = self._get_project_root() / "me" / filename
                if prompt_path.exists():
                    content = prompt_path.read_text(encoding='utf-8')
                    prompt += content + "\n\n"
                    logger.info(f"Loaded prompt from: {prompt_path}")
                else:
                    logger.warning(f"Prompt file not found: {prompt_path}")
            
            return prompt.strip() if prompt else "You are a helpful assistant."

        except Exception as e:
            logger.error(f"Error loading prompt: {e}")
            return "You are a helpful assistant."

    def _get_registry(self) -> ToolRegistry:
        """Override in subclasses to register tools."""
        return ToolRegistry()

    def _get_agent_config(self, system_prompt: str) -> AgentConfig:
        """Build agent configuration with all settings."""
        return AgentConfig(
            model=self.model_id,
            provider=self.provider_name,
            system_prompt=system_prompt,
            max_steps=self.max_steps,
            temperature=self.temperature,
            top_p=self.top_p,
            top_k=self.top_k,
            max_tokens=self.max_tokens,
            sensitive_tool_names=self.sensitive_tool_names,
            additional_params=self.additional_params,
            
            # Memory settings
            enable_memory_summarization=self.enable_memory,
            agent_name=self.agent_name or self.__class__.__name__,
            memory_recent_k=self.config.get("memory_recent_k", 10),
            memory_summarization_threshold=self.config.get("memory_summarization_threshold", 20),
            session_timeout_hours=self.config.get("session_timeout_hours", 24)
        )
        
    def create(
        self,
        system_prompt_file: Union[str, List[str]],
        agent_id: Optional[str] = None,
        set_as_current: bool = True
    ) -> Agent:
        """
        Creates and registers the agent.
        
        Note: If using database-backed memory, agent will initialize asynchronously.
        Use await agent.ensure_initialized() before first use in async contexts.
        """
        system_prompt = self._load_prompt(system_prompt_file)
        manager = get_agent_manager()
        
        if not manager._agent_factory:
            manager.set_agent_factory(create_agent)
            
        identifier = agent_id or self.__class__.__name__.lower()

        # Apply model preferences
        prefs = get_model_preferences().get_preference(identifier)
        if prefs:
            logger.info(f"Applying preferences for '{identifier}': {prefs}")
            if "model_id" in prefs: 
                self.model_id = prefs["model_id"]
            if "provider" in prefs: 
                self.provider_name = prefs["provider"]
            if "max_steps" in prefs: 
                self.max_steps = int(prefs["max_steps"])
            if "temperature" in prefs: 
                self.temperature = float(prefs["temperature"])
        
        config = self._get_agent_config(system_prompt)
        
        # Check if database is available
        db = get_global_database()
        if db and config.enable_memory_summarization:
            logger.info(f"Creating '{identifier}' with database-backed memory")
            self._initialization_pending = True
        else:
            if not db:
                logger.warning(f"No database available for '{identifier}', using in-memory fallback")
            self._initialization_pending = False
        
        # Create and register
        manager.create_and_register_agent(
            agent_id=identifier,
            config=config,
            registry=self._get_registry(),
            metadata={"created_by": self.__class__.__name__},
            set_as_current=set_as_current,
            wait_for_init=False,
        )
        
        agent = manager.get_agent(identifier)
        self._engine_agent = agent
        
        return agent
    
    async def ensure_initialized(self):
        """
        Ensure agent is initialized before use.
        Call this in async contexts before using the agent.
        
        Usage:
            agent_wrapper = MyAgent()
            agent = agent_wrapper.create("prompt.md")
            await agent_wrapper.ensure_initialized()
            # Now safe to use
        """
        if self._engine_agent and self._initialization_pending:
            manager = get_agent_manager()
            identifier = self._engine_agent.agent_id
            await manager.ensure_agent_initialized(identifier)
            self._initialization_pending = False
            logger.info(f"✅ Agent '{identifier}' ready")

    async def run(self, input_text: str) -> str:
        """
        Executes the agent with the given input.
        Automatically ensures initialization.
        """
        if not self._engine_agent:
            raise RuntimeError("Agent not initialized. Call create() first.")
        
        # Ensure initialized
        await self.ensure_initialized()
        
        return await self._engine_agent.run(input_text)

    async def stream(self, input_text: str) -> AsyncIterator[StreamChunk]:
        """
        Streams the agent execution.
        Automatically ensures initialization.
        """
        if not self._engine_agent:
            raise RuntimeError("Agent not initialized. Call create() first.")
        
        # Ensure initialized
        await self.ensure_initialized()
                
        async for chunk in self._engine_agent.stream(input_text):
            yield chunk
    
    async def start_fresh_conversation(self):
        """Start a new conversation (don't resume previous session)."""
        if not self._engine_agent:
            raise RuntimeError("Agent not initialized. Call create() first.")
        
        await self.ensure_initialized()
        
        if hasattr(self._engine_agent, 'start_fresh_conversation'):
            await self._engine_agent.start_fresh_conversation()
            logger.info(f"Started fresh conversation for {self._engine_agent.agent_id}")