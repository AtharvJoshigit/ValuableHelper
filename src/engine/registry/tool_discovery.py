
import importlib
import inspect
import os
import logging
from typing import List, Type
from engine.registry.base_tool import BaseTool

logger = logging.getLogger(__name__)

class ToolDiscovery:
    """
    Scans specified directories for Tool classes.
    """
    
    @staticmethod
    def discover_tools(include_tools_dir: bool) -> List[BaseTool]:
        """
        Finds all classes inheriting from BaseTool in the given directories.
        """
        tools = []
        directories = ['src\\engine\\registry\\library']
        if include_tools_dir :
            directories.append("src\\tools")

        for directory in directories:
            if not os.path.exists(directory):
                logger.warning(f"Discovery directory not found: {directory}")
                continue

            for root, _, files in os.walk(directory):
                for file in files:
                    if file.endswith(".py") and not file.startswith("__"):
                        file_path = os.path.join(root, file)
                        module_path = file_path.replace(os.sep, ".").replace(".py", "")
                        
                        # Handle the 'src.' prefix if necessary based on how the app is run
                        if module_path.startswith("src."):
                            module_path = module_path[4:]

                        try:
                            # Use importlib to load the module
                            # Note: For dynamic tools, they might need to be imported via file spec 
                            # if they aren't in the python path.
                            module = importlib.import_module(module_path)
                            
                            for name, obj in inspect.getmembers(module):
                                if (inspect.isclass(obj) and 
                                    issubclass(obj, BaseTool) and 
                                    obj is not BaseTool):
                                    try:
                                        # Instantiate the tool
                                        tools.append(obj())
                                        logger.info(f"Discovered and instantiated tool: {name} from {file}")
                                    except Exception as e:
                                        logger.error(f"Failed to instantiate tool {name}: {e}")
                        except Exception as e:
                            logger.error(f"Failed to import module {module_path}: {e}")
        return tools
