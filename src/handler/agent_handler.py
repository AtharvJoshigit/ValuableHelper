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
            print(agent)
            if hasattr(agent, 'chat'):
                print(f"Executing agent '{agent_name}' with chat method and arguments: {arguments}")
                result = agent.chat(**arguments)
                print(f'Result from agent {agent_name}: {result}')
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
            print(e)
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
    from src.agents.file_system_agent.files_system_agent import create_filesystem_agent
    from src.agents.research_agent.ai_research_handler import AIResearchHandler
    
    handler = AgentHandler()
    
    filesystem_agent = create_filesystem_agent(
        provider="google",
        model="gemini-3-flash-preview",
    )
    
    handler.register_agent(
        agent_name="filesystem_operations",
        agent_instance=filesystem_agent,
        description="""Perform filesystem operations including reading, writing, listing, searching files and directories.

    IMPORTANT USAGE GUIDELINES:
    - Be SPECIFIC about which operation you want (read, list, create, delete, etc.)
    - Provide EXACT file paths when possible
    - Use clear, explicit instructions

    EXAMPLES:
    ✅ Good: "Read the file src/config.py"
    ✅ Good: "Use read_file to get contents of test.txt"
    ✅ Good: "List the files in the src/ directory"
    ❌ Bad: "Check out config.py" (ambiguous)
    ❌ Bad: "Look at the src folder" (unclear operation)

    AVAILABLE OPERATIONS:
    - Read files: "Read the file [path]"
    - List directories: "List files in [path]"
    - Create files: "Create file [path] with content [text]"
    - Delete files: "Delete the file [path]"
    - Search files: "Search for files matching [pattern]"
    - And more (move, copy, get info, etc.)

    The agent will automatically preprocess your message for clarity, but explicit instructions work best.""",
        
        parameters_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Natural language description of the filesystem operation to perform. Be specific and clear about which operation (read, list, create, delete, etc.) and which file/directory path."
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Maximum number of tool execution iterations (default: 10). Increase for complex multi-step operations.",
                    "default": 10
                },
                "force_tool": {
                    "type": "string",
                    "description": "Optional: Force the agent to use a specific tool. Use when the agent consistently calls the wrong tool. Options: read_file, list_directory, create_file, delete_file, move_file, copy_file, search_files, etc.",
                    "enum": [
                        "read_file",
                        "list_directory", 
                        "create_file",
                        "overwrite_file",
                        "append_to_file",
                        "create_directory",
                        "delete_file",
                        "delete_directory",
                        "validate_path",
                        "get_file_info",
                        "move_file",
                        "copy_file",
                        "search_files",
                        "get_current_working_directory"
                    ]
                },
                "preprocess": {
                    "type": "boolean",
                    "description": "Whether to preprocess the message for clarity (default: true). Keeps enabled for best results.",
                    "default": True
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