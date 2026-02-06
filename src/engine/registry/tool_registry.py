from typing import Dict, List, Any, Optional
from .base_tool import BaseTool

class ToolRegistry:
    """
    A registry to store and manage tools available to the agent.
    """
    
    def __init__(self):
        self._tools: Dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        """
        Register a tool with the registry.
        
        Args:
            tool: The initialized tool instance to register.
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' is already registered.")
        
        self._tools[tool.name] = tool

    def get_tool(self, name: str) -> BaseTool:
        """
        Retrieve a tool by its name.
        
        Args:
            name: The name of the tool to retrieve.
            
        Returns:
            The tool instance.
            
        Raises:
            KeyError: If the tool is not found.
        """
        if name not in self._tools:
            raise KeyError(f"Tool '{name}' not found in registry.")
        return self._tools[name]
    
    def get_all_tools(self) -> List[BaseTool]:
        """
        Get a list of all registered tools.
        """
        return list(self._tools.values())

    def export_for(self, provider_type: str) -> List[Dict[str, Any]]:
        """
        Export tools definitions for a specific provider.
        
        Args:
            provider_type: The identifier for the provider (e.g., 'google', 'openai').
            
        Returns:
            A list of tool definitions including name, description, and parameter schema.
        """
        # In Phase 2, we return a standardized dictionary containing all necessary info.
        # Provider adapters (Phase 3) will transform this into provider-specific objects.
        
        tool_definitions = []
        for tool in self._tools.values():
            tool_definitions.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.get_schema()
            })
            
        return tool_definitions
