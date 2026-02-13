from agents.agent_id import AGENT_ID
from agents.base_agent import BaseAgent
from engine.registry.tool_registry import ToolRegistry
from tools.web_search_tool import WebSearchTool
from tools.web_scraper_tool import WebScraperTool

class ResearchAgent(BaseAgent):
    """
    Specialized agent for research tasks with web search and scraping capabilities.
    """
    
    def __init__(self, config: dict = None):
        default_config = {
            "model_id": "gemini-2.5-pro",
            "provider": "google",
            "max_steps": 20,
            "temperature": 0.7
        }
        if config:
            default_config.update(config)
        super().__init__(default_config)
    
    def _get_registry(self) -> ToolRegistry:
        """Register research-specific tools."""
        registry = ToolRegistry()
        registry.register(WebSearchTool())
        registry.register(WebScraperTool())
        return registry
    
    def start(self):
        return self.create(
            system_prompt_file=["my_agents/research_agent.md", "tools_call.md"],
            agent_id=AGENT_ID.FIXED_RESEARCH_AGENT.value,
            set_as_current=False
        )
