from pathlib import Path
from typing import Optional
from engine.core.agent import Agent
from engine.providers.base_provider import BaseProvider
from engine.providers.google.provider import GoogleProvider
from engine.registry.tool_registry import ToolRegistry

class BaseAgent:
    def __init__(self, config: Optional[dict] = None):
        self.config = config or {}
        # Set default model if not in config
        self.model_id = self.config.get("model_id", "gemini-2.0-flash-exp")

    def _get_project_root(self) -> Path:
        """Dynamically finds the project root."""
        return Path(__file__).resolve().parents[2]

    def _load_prompt(self, filename: str) -> str:
        """Loads a markdown prompt from the me/ directory."""
        try:
            prompt_path = self._get_project_root() / "me" / filename
            if prompt_path.exists():
                return prompt_path.read_text(encoding='utf-8')
        except Exception as e:
            print(f"⚠️  Error loading prompt {filename}: {e}")
        return "You are a helpful assistant."

    def _get_provider(self) -> BaseProvider:
        return GoogleProvider(model_id=self.model_id)

    def _get_registry(self) -> ToolRegistry:
        """Override this in subclasses to add specific tools."""
        return ToolRegistry()

    def create(self, system_prompt_file: str) -> Agent:
        """Factory method to assemble the agent."""
        return Agent(
            provider=self._get_provider(),
            registry=self._get_registry(),
            system_prompt=self._load_prompt(system_prompt_file)
        )