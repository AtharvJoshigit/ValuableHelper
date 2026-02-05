"""
Agent and Tool Setup - Modular Configuration

This file handles all agent and tool registration.
Easy to add new agents/tools by just adding registration calls.
"""
from src.main_agent.agent_tool_handler import AgentToolHandler
from typing import Optional


def setup_all_agents_and_tools(
    filesystem_provider: str = "google",
    filesystem_model: str = "gemini-3-flash-preview"
) -> AgentToolHandler:
    """
    Setup all agents and tools.
    
    Returns:
        Configured AgentToolHandler with all agents and tools registered
    """
    handler = AgentToolHandler(max_parallel_workers=5)
    
    # Register all agents
    register_filesystem_agent(handler, filesystem_provider, filesystem_model)
    register_research_agents(handler)
    
    # Register all tools
    register_utility_tools(handler)
    
    # Print summary
    print("\n" + "=" * 60)
    print("AGENT/TOOL REGISTRATION SUMMARY")
    print("=" * 60)
    print(f"Agents registered: {len(handler.list_agents())}")
    for agent in handler.list_agents():
        print(f"  • {agent}")
    print(f"\nTools registered: {len(handler.list_tools())}")
    for tool in handler.list_tools():
        print(f"  • {tool}")
    print("=" * 60 + "\n")
    
    return handler


def register_filesystem_agent(
    handler: AgentToolHandler,
    provider: str = "google",
    model: str = "gemini-2.0-flash-exp"
):
    """Register the filesystem operations agent."""
    from src.agents.file_system_agent.files_system_agent import create_filesystem_agent
    
    filesystem_agent = create_filesystem_agent(
        provider=provider,
        model=model,
        debug=True
    )
    
    handler.register_agent(
        name="filesystem_operations",
        instance=filesystem_agent,
        description="""Perform filesystem operations (read, write, list, search files/directories).

USAGE: Be specific and clear:
✅ "Read the file src/config.py"
✅ "List files in src/agents/"
✅ "Create file test.txt with content 'hello'"

OPERATIONS: read, list, create, delete, move, copy, search""",
        
        parameters_schema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Filesystem operation. Be specific: 'Read file X', 'List directory Y'"
                },
                "max_iterations": {
                    "type": "integer",
                    "description": "Max iterations (default: 10)",
                    "default": 10
                },
                "force_tool": {
                    "type": "string",
                    "description": "Force specific tool (optional)",
                    "enum": [
                        "read_file", "list_directory", "create_file",
                        "delete_file", "move_file", "copy_file"
                    ]
                },
                "preprocess": {
                    "type": "boolean",
                    "description": "Preprocess message (default: true)",
                    "default": True
                }
            },
            "required": ["message"]
        },
        parallel_safe=True,  # Can run in parallel with other agents
        metadata={"category": "filesystem", "provider": provider}
    )


def register_research_agents(handler: AgentToolHandler):
    """Register all research-related agents."""
    from src.agents.research_agent.ai_research_handler import AIResearchHandler
    
    research_handler = AIResearchHandler()
    
    # Research - General
    handler.register_agent(
        name="research_general",
        instance=lambda topic, include_images=False, output_format="text":
            research_handler.handle_research(topic, include_images, output_format),
        description="Conduct comprehensive research on any topic. Returns detailed research reports.",
        parameters_schema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to research"
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Generate related images",
                    "default": False
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "description": "Output format",
                    "default": "text"
                }
            },
            "required": ["topic"]
        },
        parallel_safe=True,  # Can run in parallel
        metadata={"category": "research", "type": "general"}
    )
    
    # Research - Trends
    handler.register_agent(
        name="research_trends",
        instance=lambda topic, include_images=False, output_format="text":
            research_handler.handle_research_on_trend(topic, include_images, output_format),
        description="Analyze current trends and future predictions on a topic.",
        parameters_schema={
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "Topic to analyze trends for"
                },
                "include_images": {
                    "type": "boolean",
                    "description": "Generate trend visualizations",
                    "default": False
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "text"
                }
            },
            "required": ["topic"]
        },
        parallel_safe=True,
        metadata={"category": "research", "type": "trends"}
    )
    
    # Research - Daily Digest
    handler.register_agent(
        name="daily_research_digest",
        instance=lambda categories=None, include_images=False, output_format="text":
            research_handler.todays_research(include_images, output_format, categories),
        description="Generate comprehensive daily research digest covering multiple categories.",
        parameters_schema={
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Categories to include (e.g., ['AI', 'Space'])",
                    "default": None
                },
                "include_images": {
                    "type": "boolean",
                    "default": False
                },
                "output_format": {
                    "type": "string",
                    "enum": ["text", "json"],
                    "default": "text"
                }
            },
            "required": []
        },
        parallel_safe=False,  # Might be resource-intensive
        metadata={"category": "research", "type": "digest"}
    )


def register_utility_tools(handler: AgentToolHandler):
    """Register utility tools (simple functions)."""
    
    # Calculator tool
    def calculator(expression: str) -> dict:
        """Evaluate a mathematical expression."""
        try:
            result = eval(expression, {"__builtins__": {}}, {})
            return {"status": "success", "result": result}
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    handler.register_tool(
        name="calculator",
        function=calculator,
        description="Evaluate mathematical expressions. Example: '2 + 2 * 3'",
        parameters_schema={
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "Mathematical expression to evaluate"
                }
            },
            "required": ["expression"]
        },
        parallel_safe=True,
        metadata={"category": "utility"}
    )
    
    # Get current time tool
    def get_current_time(timezone: str = "UTC") -> dict:
        """Get current time in specified timezone."""
        from datetime import datetime
        import pytz
        
        try:
            tz = pytz.timezone(timezone)
            current_time = datetime.now(tz)
            return {
                "status": "success",
                "time": current_time.isoformat(),
                "timezone": timezone,
                "formatted": current_time.strftime("%Y-%m-%d %H:%M:%S %Z")
            }
        except Exception as e:
            return {"status": "error", "error": str(e)}
    
    handler.register_tool(
        name="get_current_time",
        function=get_current_time,
        description="Get current time in a specific timezone.",
        parameters_schema={
            "type": "object",
            "properties": {
                "timezone": {
                    "type": "string",
                    "description": "Timezone (e.g., 'America/New_York', 'Asia/Tokyo')",
                    "default": "UTC"
                }
            },
            "required": []
        },
        parallel_safe=True,
        metadata={"category": "utility"}
    )


# Example: How to add a new agent
def example_add_new_agent(handler: AgentToolHandler):
    """
    Example of how to add a new agent.
    
    Just copy this pattern and modify for your agent!
    """
    
    # 1. Import or create your agent
    # from my_agents.cool_agent import CoolAgent
    # cool_agent = CoolAgent()
    
    # 2. Register it
    # handler.register_agent(
    #     name="cool_agent",
    #     instance=cool_agent,
    #     description="Does cool things",
    #     parameters_schema={
    #         "type": "object",
    #         "properties": {
    #             "input": {
    #                 "type": "string",
    #                 "description": "What to do"
    #             }
    #         },
    #         "required": ["input"]
    #     },
    #     parallel_safe=True
    # )
    pass


# Example: How to add a new tool
def example_add_new_tool(handler: AgentToolHandler):
    """
    Example of how to add a new tool.
    
    Just copy this pattern and modify for your tool!
    """
    
    # 1. Define your tool function
    # def my_tool(param1: str, param2: int = 10) -> dict:
    #     """Do something useful."""
    #     try:
    #         result = f"Processed {param1} with {param2}"
    #         return {"status": "success", "result": result}
    #     except Exception as e:
    #         return {"status": "error", "error": str(e)}
    
    # 2. Register it
    # handler.register_tool(
    #     name="my_tool",
    #     function=my_tool,
    #     description="Does something useful with params",
    #     parameters_schema={
    #         "type": "object",
    #         "properties": {
    #             "param1": {
    #                 "type": "string",
    #                 "description": "First parameter"
    #             },
    #             "param2": {
    #                 "type": "integer",
    #                 "description": "Second parameter",
    #                 "default": 10
    #             }
    #         },
    #         "required": ["param1"]
    #     },
    #     parallel_safe=True
    # )
    pass