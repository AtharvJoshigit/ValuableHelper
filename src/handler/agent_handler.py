# file: agent_handler.py

from typing import Dict, Any, List, Optional, Callable
import json
from dataclasses import dataclass, asdict


@dataclass
class AgentToolResult:
    status: str
    agent_name: str
    result: Any
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


class AgentHandler:
    def __init__(self):
        self.agents: Dict[str, Any] = {}
        self.agent_configs: Dict[str, Dict[str, Any]] = {}
    
    def register_agent(
        self,
        agent_name: str,
        agent_instance: Any,
        description: str,
        parameters_schema: Dict[str, Any]
    ):
        self.agents[agent_name] = agent_instance
        self.agent_configs[agent_name] = {
            "description": description,
            "parameters": parameters_schema
        }
    
    def get_tools_schema(self) -> List[Dict[str, Any]]:
        tools = []
        for agent_name, config in self.agent_configs.items():
            tools.append({
                "type": "function",
                "function": {
                    "name": agent_name,
                    "description": config["description"],
                    "parameters": config["parameters"]
                }
            })
        return tools
    
    def execute_agent(
        self,
        agent_name: str,
        arguments: Dict[str, Any]
    ) -> AgentToolResult:
        if agent_name not in self.agents:
            return AgentToolResult(
                status="error",
                agent_name=agent_name,
                result=None,
                error=f"Agent '{agent_name}' not found"
            )
        
        try:
            agent = self.agents[agent_name]
            
            if hasattr(agent, 'chat'):
                result = agent.chat(**arguments)
            elif callable(agent):
                result = agent(**arguments)
            else:
                return AgentToolResult(
                    status="error",
                    agent_name=agent_name,
                    result=None,
                    error=f"Agent '{agent_name}' is not callable"
                )
            
            return AgentToolResult(
                status="success",
                agent_name=agent_name,
                result=result,
                metadata={"arguments": arguments}
            )
        
        except Exception as e:
            return AgentToolResult(
                status="error",
                agent_name=agent_name,
                result=None,
                error=str(e),
                metadata={"arguments": arguments}
            )
    
    def execute_multiple(
        self,
        tool_calls: List[Dict[str, Any]]
    ) -> List[AgentToolResult]:
        results = []
        for tool_call in tool_calls:
            agent_name = tool_call.get("function", {}).get("name")
            arguments = tool_call.get("function", {}).get("arguments", {})
            
            if isinstance(arguments, str):
                arguments = json.loads(arguments)
            
            result = self.execute_agent(agent_name, arguments)
            results.append(result)
        
        return results


def create_agent_handler() -> AgentHandler:
    from src.agents.file_system_agent.file_system_handler import create_filesystem_agent
    from src.agents.research_agent.ai_research_handler import AIResearchHandler
    
    handler = AgentHandler()
    
    filesystem_agent = create_filesystem_agent(
        provider="google",
        model="gemini-3-flash-preview",
    )
    
    handler.register_agent(
        agent_name="filesystem_operations",
        agent_instance=filesystem_agent,
        description="Perform filesystem operations including reading, writing, listing, searching files and directories. Use this agent for any file system related tasks.",
        parameters_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Natural language description of the filesystem operation to perform"
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum number of tool execution iterations",
                    "default": 10
                }
            },
            "required": ["message"]
        }
    )
    
    research_agent = AIResearchHandler()
    
    handler.register_agent(
        agent_name="research_general",
        agent_instance=lambda topic, include_images=False, output_format="text": 
            research_agent.handle_research(topic, include_images, output_format),
        description="Conduct comprehensive research on any topic. Returns detailed research reports with optional images.",
        parameters_schema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to research"
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Whether to generate related images",
                    "default": False
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "description": "Output format for research results",
                    "default": "text"
                }
            },
            "required": ["topic"]
        }
    )
    
    handler.register_agent(
        agent_name="research_trends",
        agent_instance=lambda topic, include_images=False, output_format="text":
            research_agent.handle_research_on_trend(topic, include_images, output_format),
        description="Analyze current trends and developments on a specific topic. Focuses on what's trending now and future predictions.",
        parameters_schema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic to analyze trends for"
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Whether to generate trend visualization images",
                    "default": False
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "description": "Output format for trend analysis",
                    "default": "text"
                }
            },
            "required": ["topic"]
        }
    )
    
    handler.register_agent(
        agent_name="daily_research_digest",
        agent_instance=lambda categories=None, include_images=False, output_format="text":
            research_agent.todays_research(include_images, output_format, categories),
        description="Generate a comprehensive daily research digest covering multiple categories. Perfect for daily briefings and updates.",
        parameters_schema={
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of categories to include in the digest (e.g., ['AI', 'Space', 'Health'])",
                    "default": None
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Whether to generate digest cover image",
                    "default": False
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "description": "Output format for the digest",
                    "default": "text"
                }
            },
            "required": []
        }
    )
    
    return handler