# file: src/agents/base_agent.py

from pathlib import Path
from typing import Optional, Set, Union, List, AsyncIterator
from engine.core.agent import Agent
from engine.core.agent_factory import create_agent
from engine.registry.tool_registry import ToolRegistry
from engine.core.agent_instance_manager import AgentConfig, get_agent_manager
from engine.core.types import StreamChunk
from services.model_preferences import get_model_preferences
import logging

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for creating specialized agent types.
    Can act as both a Factory (creating specific configs) and a Wrapper (holding an active instance).
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        # Default values (can be overridden by subclasses or preferences)
        self.model_id = self.config.get("model_id", "gemini-2.5-pro")
        self.provider_name = self.config.get("provider", "google")
        self.max_steps = self.config.get("max_steps", 20)
        self.temperature = self.config.get("temperature", 0.7)
        self.top_p = self.config.get("top_p", None)
        self.top_k = self.config.get("top_k", None)
        self.max_tokens = self.config.get("max_tokens", None)
        self.sensitive_tool_names: Set[str] = self.config.get("sensitive_tool_names", set())
        self.additional_params = self.config.get("additional_params", {})
        
        # The active engine instance if this class is used as a wrapper
        self._engine_agent: Optional[Agent] = None

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
            additional_params=self.additional_params
        )
        
    def create(
        self,
        system_prompt_file: Union[str, List[str]],
        agent_id: Optional[str] = None,
        set_as_current: bool = True
    ) -> Agent:
        """
        Creates and registers the agent. 
        Always overwrites any existing agent with the same ID to ensure fresh config and tools.
        """
        system_prompt = self._load_prompt(system_prompt_file)
        manager = get_agent_manager()
        
        if not manager._agent_factory:
            manager.set_agent_factory(create_agent)
            
        identifier = agent_id or self.__class__.__name__.lower()

        # --- PREFERENCE OVERRIDE ---
        # Check if there are saved preferences for this agent
        prefs = get_model_preferences().get_preference(identifier)
        if prefs:
            logger.info(f"Applying persistent model preferences for '{identifier}': {prefs}")
            # We temporarily update the instance attributes so _get_agent_config uses them
            if "model_id" in prefs: self.model_id = prefs["model_id"]
            if "provider" in prefs: self.provider_name = prefs["provider"]
            if "max_steps" in prefs: self.max_steps = int(prefs["max_steps"])
            if "temperature" in prefs: self.temperature = float(prefs["temperature"])
            # Add other overrides as needed
        # ---------------------------
        
        config = self._get_agent_config(system_prompt)
        
        
        # Always create fresh to ensure registry is populated correctly.
        manager.create_and_register_agent(
            agent_id=identifier,
            config=config,
            registry=self._get_registry(),
            metadata={"created_by": self.__class__.__name__},
            set_as_current=set_as_current
        )
        agent = manager.get_agent(identifier)

        self._engine_agent = agent
        return agent

    async def run(self, input_text: str) -> str:
        """
        Executes the agent with the given input. 
        Requires the agent to be initialized via create().
        """
        if not self._engine_agent:
             raise RuntimeError("Agent not initialized. Call create() first.")
        
        return await self._engine_agent.run(input_text)

    async def stream(self, input_text: str) -> AsyncIterator[StreamChunk]:
        """
        Streams the agent execution.
        """
        if not self._engine_agent:
            raise RuntimeError("Agent not initialized. Call create() first.")
                
        async for chunk in self._engine_agent.stream(input_text):
            yield chunk
