import importlib
import inspect
import os
import logging
import sys
from typing import List
from engine.registry.base_tool import BaseTool

logger = logging.getLogger(__name__)

class ToolDiscovery:
    """
    Scans specified directories for Tool classes dynamically.
    """
    
    @staticmethod
    def discover_tools(search_dirs: List[str] = ["tools"]) -> List[BaseTool]:
        """
        Finds all classes inheriting from BaseTool in the project.
        
        Strategy:
        1. Locate the 'src' root.
        2. Walk through 'engine/registry/library' and 'tools'.
        3. Dynamic import using relative module paths.
        4. Instantiate found classes.
        """
        tools = []
        
        # 1. Determine the root 'src' directory dynamically
        # This file is likely in src/engine/registry/tool_discovery.py
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # Go up two levels to reach 'src' (registry -> engine -> src)
        src_root = os.path.abspath(os.path.join(current_dir, "..", ".."))
        
        # 2. Add src to sys.path if not present (crucial for imports like 'engine.registry...')
        if src_root not in sys.path:
            sys.path.insert(0, src_root)

        for relative_dir in search_dirs:
            abs_dir_path = os.path.join(src_root, relative_dir)
            
            if not os.path.exists(abs_dir_path):
                logger.warning(f"Tool Discovery: Directory not found: {abs_dir_path}")
                continue

            # Walk the directory
            for root, _, files in os.walk(abs_dir_path):
                for file in files:
                    # Skip __init__.py and non-python files
                    if file.endswith(".py") and not file.startswith("__"):
                        file_path = os.path.join(root, file)
                        
                        # Calculate module path: e.g., engine.registry.library.my_tool
                        # We strip the src_root prefix to get the package path
                        try:
                            rel_path = os.path.relpath(file_path, src_root)
                            # Convert file path to module dotted path
                            module_name = rel_path.replace(os.sep, ".")[:-3] # remove .py
                            
                            # Import
                            module = importlib.import_module(module_name)
                            
                            # Inspect
                            for name, obj in inspect.getmembers(module):
                                if (inspect.isclass(obj) and 
                                    issubclass(obj, BaseTool) and 
                                    obj is not BaseTool):
                                    
                                    try:
                                        # Check if we already found this exact class (avoid duplicates)
                                        # (e.g., if imported in multiple places)
                                        if any(t.__class__ == obj for t in tools):
                                            continue
                                            
                                        # Instantiate the tool
                                        # Note: This assumes __init__ requires no arguments or has defaults.
                                        instance = obj()
                                        tools.append(instance)
                                        logger.info(f"Discovered tool: {instance.name} (from {module_name})")
                                    except Exception as e:
                                        logger.error(f"Failed to instantiate tool {name} in {module_name}: {e}")
                                        
                        except Exception as e:
                            logger.error(f"Failed to process module from {file_path}: {e}")
                            
        return tools
