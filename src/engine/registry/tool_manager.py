import logging
import importlib
from typing import List, Optional
from engine.registry.tool_discovery import ToolDiscovery
from rag.stores.tools import ToolVectorStore
from engine.registry.base_tool import BaseTool

logger = logging.getLogger(__name__)

class ToolManager:
    """
    Manages the lifecycle of tools:
    1. Sync: Discovery -> Vector DB Indexing
    2. Retrieve: Semantic Search -> Dynamic Instantiation
    """
    
    def __init__(self):
        self.store = ToolVectorStore()
        
    def delete_collection(self) : 
        logger.info("Clearing previous Collection...")
        self.store.clear()

    def sync_tools(self) -> None:
        """
        Scans for tools and updates the vector database index.
        """
        logger.info("Starting Tool Sync...")
        
        # 1. Discover existing tools in codebase
        discovered_tools: List[BaseTool] = ToolDiscovery.discover_tools()
        
        if not discovered_tools:
            logger.warning("No tools discovered to sync.")
            return

        # 2. Index them
        count = 0
        for tool in discovered_tools:
            try:
                # Extract Python location info
                module_path = tool.__class__.__module__
                class_name = tool.__class__.__name__
                
                # Construct data for schema
                tool_data = {
                    "name": tool.name,
                    "id": tool.name, 
                    "purpose": tool.__doc__ or "", # Fallback if no explicit purpose
                    "description": tool.description,
                    "version": "1.0", # Default
                    "module_path": module_path,
                    "class_name": class_name
                }
                
                self.store.add_tool(tool_data)
                count += 1
                logger.info(f"Indexed tool: {tool.name}")
            except Exception as e:
                logger.error(f"Failed to index tool {tool.name}: {e}")

        logger.info(f"Tool Sync Complete. Indexed {count} tools.")

    def retrieve_tools(self, query: str, limit: int = 5) -> List[BaseTool]:
        """
        Semantically searches for tools and returns instantiated objects.
        """

        tool_metadata_list = self.store.find_tools(query, limit=limit)
        instantiated_tools = []

        for meta in tool_metadata_list:
            module_path = meta.get("module_path")
            class_name = meta.get("class_name")
            
            if not module_path or not class_name:
                logger.error(f"Tool metadata missing location info: {meta}")
                continue
                
            try:
                # Dynamic Import
                module = importlib.import_module(module_path)
                cls = getattr(module, class_name)
                
                # Instantiate
                # Assuming 0-arg constructor or defaults, which BaseTool usually supports
                tool_instance = cls()
                instantiated_tools.append(tool_instance)
                
            except Exception as e:
                logger.error(f"Failed to load tool {class_name} from {module_path}: {e}")
        
        return instantiated_tools
