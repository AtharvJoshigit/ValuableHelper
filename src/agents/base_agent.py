# file: engine/core/base_agent.py

from pathlib import Path
from typing import Optional, Set, Union, List
from engine.core.agent import Agent
from engine.core.agent_factory import create_agent
from engine.registry.tool_registry import ToolRegistry
from engine.core.agent_instance_manager import AgentConfig, get_agent_manager
import logging

logger = logging.getLogger(__name__)


class BaseAgent:
    """
    Base class for creating specialized agent types with custom configurations.
    Subclass this to create agents with specific tools, prompts, and behaviors.
    """
    
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        self.model_id = self.config.get("model_id", "gemini-2.5-flash")
        self.provider_name = self.config.get("provider", "google")
        self.max_steps = self.config.get("max_steps", 20)
        self.temperature = self.config.get("temperature", 0.7)
        self.top_p = self.config.get("top_p", None)
        self.top_k = self.config.get("top_k", None)
        self.max_tokens = self.config.get("max_tokens", None)
        self.sensitive_tool_names: Set[str] = self.config.get("sensitive_tool_names", set())
        self.additional_params = self.config.get("additional_params", {})

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
        """
        Override this in subclasses to add specific tools.
        
        Example:
            def _get_registry(self) -> ToolRegistry:
                registry = ToolRegistry()
                registry.register(WebSearchTool())
                registry.register(CodeExecutorTool())
                return registry
        """
        return ToolRegistry()

    def _get_agent_config(self, system_prompt: str) -> AgentConfig:
        """
        Create agent configuration. Override to customize config creation.
        
        Args:
            system_prompt: The loaded system prompt
            
        Returns:
            AgentConfig instance
        """
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

    async def run(self):
        raise NotImplementedError

        
    def create(
        self,
        system_prompt_file: Union[str, List[str]],
        agent_id: Optional[str] = None,
        set_as_current: bool = True
    ) -> Agent:
        """
        Factory method to create and register the agent using AgentInstanceManager.
        
        Args:
            system_prompt_file: Filename(s) in me/ directory to load as system prompt
            agent_id: Unique identifier for this agent (defaults to class name)
            set_as_current: Whether to set this as the current active agent
            
        Returns:
            Created Agent instance
            
        Example:
            class ResearchAgent(BaseAgent):
                def _get_registry(self):
                    registry = ToolRegistry()
                    registry.register(WebSearchTool())
                    return registry
            
            agent = ResearchAgent().create("research_prompt.md", agent_id="researcher")
        """
        system_prompt = self._load_prompt(system_prompt_file)
        
        manager = get_agent_manager()
        
        if not manager._agent_factory:
            manager.set_agent_factory(create_agent)
            logger.info("Set agent factory in manager")
        
        config = self._get_agent_config(system_prompt)
        identifier = agent_id or self.__class__.__name__.lower()
        
        existing_agent = manager.get_agent(identifier)
        if existing_agent:
            logger.warning(f"Agent '{identifier}' already exists. Updating configuration.")
            manager.update_agent(
                agent_id=identifier,
                model=config.model,
                provider=config.provider,
                system_prompt=config.system_prompt,
                max_steps=config.max_steps,
                temperature=config.temperature,
                top_p=config.top_p,
                top_k=config.top_k,
                max_tokens=config.max_tokens,
                sensitive_tool_names=config.sensitive_tool_names,
                preserve_memory=False,
                preserve_registry=False,
                **config.additional_params
            )
            
            if set_as_current:
                manager.set_current_agent(identifier)
            
            agent = manager.get_agent(identifier)
        else:
            manager.create_and_register_agent(
                agent_id=identifier,
                config=config,
                registry=self._get_registry(),
                metadata={
                    "created_by": self.__class__.__name__,
                    "prompt_files": system_prompt_file if isinstance(system_prompt_file, list) else [system_prompt_file]
                },
                set_as_current=set_as_current
            )
            
            agent = manager.get_agent(identifier)
        
        if not agent:
            raise RuntimeError(f"Failed to retrieve agent '{identifier}' from manager")
        
        logger.info(
            f"Created agent '{identifier}' with model={config.model}, "
            f"provider={config.provider}, max_steps={config.max_steps}"
        )
        
        return agent

    def get_or_create(
        self,
        system_prompt_file: Union[str, List[str]],
        agent_id: Optional[str] = None,
        set_as_current: bool = True
    ) -> Agent:
        """
        Get existing agent or create new one if it doesn't exist.
        
        Args:
            system_prompt_file: Filename(s) in me/ directory to load as system prompt
            agent_id: Unique identifier for this agent
            set_as_current: Whether to set as current if creating new
            
        Returns:
            Agent instance
        """
        identifier = agent_id or self.__class__.__name__.lower()
        manager = get_agent_manager()
        
        existing = manager.get_agent(identifier)
        if existing:
            logger.info(f"Using existing agent: {identifier}")
            if set_as_current:
                manager.set_current_agent(identifier)
            return existing
        
        return self.create(system_prompt_file, agent_id, set_as_current)