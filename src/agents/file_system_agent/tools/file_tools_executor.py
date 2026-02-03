"""
FileSystem Tools Schema and Executor - IMPROVED VERSION

FIXES:
1. Removed unused import
2. Added parameter validation
3. Added better error handling with logging
4. Added type hints throughout
5. Added comprehensive docstrings
6. Added debug mode
7. Better exception handling
"""

import json
import traceback
from typing import Dict, Any, List, Optional, Callable


FILESYSTEM_TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "get_current_working_directory",
            "description": "Get the current working directory path",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "List files and directories in a given path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Directory path to list. If not provided, lists current directory"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to list recursively (all subdirectories)",
                        "default": False
                    },
                    "include_hidden": {
                        "type": "boolean",
                        "description": "Whether to include hidden files and directories",
                        "default": False
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read the contents of a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to read"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_file",
            "description": "Create a new file with content",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path where the file should be created"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write to the file",
                        "default": ""
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "overwrite_file",
            "description": "Overwrite an existing file with new content",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to overwrite"
                    },
                    "content": {
                        "type": "string",
                        "description": "New content for the file"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "append_to_file",
            "description": "Append content to an existing file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to append to"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to append to the file"
                    },
                    "encoding": {
                        "type": "string",
                        "description": "File encoding",
                        "default": "utf-8"
                    }
                },
                "required": ["file_path", "content"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_directory",
            "description": "Create a new directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Path where the directory should be created"
                    }
                },
                "required": ["directory_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_file",
            "description": "Delete a file",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file to delete"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "delete_directory",
            "description": "Delete a directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "directory_path": {
                        "type": "string",
                        "description": "Path to the directory to delete"
                    },
                    "recursive": {
                        "type": "boolean",
                        "description": "Whether to delete directory recursively (including all contents)",
                        "default": False
                    }
                },
                "required": ["directory_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "validate_path",
            "description": "Validate and get information about a path",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Path to validate"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_file_info",
            "description": "Get detailed information about a file or directory",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Path to the file or directory"
                    }
                },
                "required": ["file_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "move_file",
            "description": "Move a file or directory to a new location",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Current path of the file or directory"
                    },
                    "destination_path": {
                        "type": "string",
                        "description": "New path for the file or directory"
                    }
                },
                "required": ["source_path", "destination_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "copy_file",
            "description": "Copy a file to a new location",
            "parameters": {
                "type": "object",
                "properties": {
                    "source_path": {
                        "type": "string",
                        "description": "Path to the source file"
                    },
                    "destination_path": {
                        "type": "string",
                        "description": "Path where the file should be copied"
                    }
                },
                "required": ["source_path", "destination_path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "search_files",
            "description": "Search for files matching a pattern",
            "parameters": {
                "type": "object",
                "properties": {
                    "pattern": {
                        "type": "string",
                        "description": "Search pattern (filename or glob pattern)"
                    },
                    "search_path": {
                        "type": "string",
                        "description": "Directory to search in. If not provided, searches current directory"
                    },
                    "case_sensitive": {
                        "type": "boolean",
                        "description": "Whether the search should be case-sensitive",
                        "default": False
                    }
                },
                "required": ["pattern"]
            }
        }
    }
]


class FileSystemToolExecutor:
    """
    Executor for filesystem tool calls from LLM function calling.
    
    This class handles:
    - Validation of function arguments against schema
    - Execution of filesystem operations
    - Error handling and logging
    - Support for both single and batch tool execution
    
    Example:
        >>> executor = FileSystemToolExecutor(
        ...     filesystem_functions={
        ...         'read_file': my_read_function,
        ...         'create_file': my_create_function
        ...     },
        ...     debug=True
        ... )
        >>> result = executor.execute_tool_call({
        ...     'function': {
        ...         'name': 'read_file',
        ...         'arguments': {'file_path': 'test.txt'}
        ...     }
        ... })
    """
    
    def __init__(
        self, 
        filesystem_functions: Dict[str, Callable],
        tool_schema: Optional[List[Dict[str, Any]]] = None,
        debug: bool = False
    ) -> None:
        """
        Initialize the tool executor.
        
        Args:
            filesystem_functions: Dictionary mapping function names to callable functions.
                                 Each function should accept keyword arguments matching
                                 its schema and return a dict with 'status' and result/error.
            tool_schema: Optional custom tool schema. If not provided, uses FILESYSTEM_TOOLS_SCHEMA.
            debug: If True, prints debug information during execution.
        """
        self.functions = filesystem_functions
        self.tool_schema = tool_schema or FILESYSTEM_TOOLS_SCHEMA
        self.debug = debug
        
        # Validate that all schema functions have corresponding implementations
        if debug:
            self._validate_schema_coverage()
    
    def _validate_schema_coverage(self) -> None:
        """Validate that all schema functions have implementations."""
        schema_functions = {t["function"]["name"] for t in self.tool_schema}
        implemented_functions = set(self.functions.keys())
        
        missing = schema_functions - implemented_functions
        extra = implemented_functions - schema_functions
        
        if missing:
            print(f"⚠️  Warning: Schema defines functions not implemented: {missing}")
        if extra:
            print(f"ℹ️  Info: Implemented functions not in schema: {extra}")
    
    def _log(self, message: str) -> None:
        """Log debug messages if debug mode is enabled."""
        if self.debug:
            print(f"[FileSystemToolExecutor] {message}")
    
    def _validate_arguments(
        self, 
        function_name: str, 
        arguments: Dict[str, Any]
    ) -> Optional[str]:
        """
        Validate arguments against the tool schema.
        
        Args:
            function_name: Name of the function to validate
            arguments: Arguments dictionary to validate
            
        Returns:
            Error message string if validation fails, None if valid
        """
        # Find the tool schema for this function
        tool_schema = next(
            (t for t in self.tool_schema if t["function"]["name"] == function_name),
            None
        )
        
        if not tool_schema:
            return f"No schema found for function: {function_name}"
        
        # Check required parameters
        required = tool_schema["function"]["parameters"].get("required", [])
        missing = [r for r in required if r not in arguments]
        
        if missing:
            return f"Missing required parameters: {', '.join(missing)}"
        
        # Check for unexpected parameters (optional, strict validation)
        if self.debug:
            properties = tool_schema["function"]["parameters"].get("properties", {})
            unexpected = [k for k in arguments.keys() if k not in properties]
            if unexpected:
                self._log(f"Note: Unexpected parameters (may be ignored): {unexpected}")
        
        return None
    
    def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a single tool call.
        
        Args:
            tool_call: Dictionary containing:
                - id: (Optional) Tool call ID for tracking
                - function: Dictionary with:
                    - name: Function name to execute
                    - arguments: Dictionary or JSON string of arguments
                
        Returns:
            Dictionary with execution result:
                - status: "success" or "error"
                - For success: includes function-specific return values
                - For error: includes "error" field with error message
                
        Example:
            >>> executor.execute_tool_call({
            ...     'id': 'call_123',
            ...     'function': {
            ...         'name': 'create_file',
            ...         'arguments': {'file_path': 'test.txt', 'content': 'Hello'}
            ...     }
            ... })
            {'status': 'success', 'file_path': 'test.txt', 'created': True}
        """
        function_name = tool_call.get("function", {}).get("name")
        arguments = tool_call.get("function", {}).get("arguments", {})
        
        self._log(f"Executing: {function_name}")
        self._log(f"Arguments: {arguments}")
        
        # Parse arguments if they're a JSON string
        if isinstance(arguments, str):
            try:
                arguments = json.loads(arguments)
                self._log(f"Parsed JSON arguments: {arguments}")
            except json.JSONDecodeError as e:
                error_msg = f"Invalid JSON arguments: {str(e)}"
                self._log(f"❌ {error_msg}")
                return {
                    "status": "error",
                    "error": error_msg
                }
        
        # Check if function exists
        if function_name not in self.functions:
            error_msg = f"Unknown function: {function_name}"
            self._log(f"❌ {error_msg}")
            return {
                "status": "error",
                "error": error_msg,
                "available_functions": list(self.functions.keys())
            }
        
        # Validate arguments against schema
        validation_error = self._validate_arguments(function_name, arguments)
        if validation_error:
            self._log(f"❌ Validation error: {validation_error}")
            return {
                "status": "error",
                "error": validation_error
            }
        
        # Execute the function
        try:
            result = self.functions[function_name](**arguments)
            self._log(f"✅ Success: {function_name}")
            return result
            
        except TypeError as e:
            # This usually means wrong parameter names or types
            error_msg = f"Invalid arguments for {function_name}: {str(e)}"
            self._log(f"❌ TypeError: {error_msg}")
            
            if self.debug:
                print(traceback.format_exc())
            
            return {
                "status": "error",
                "error": error_msg,
                "hint": "Check parameter names and types match the schema"
            }
            
        except Exception as e:
            # Catch all other errors
            error_msg = f"Error executing {function_name}: {str(e)}"
            self._log(f"❌ Exception: {error_msg}")
            
            if self.debug:
                print("Full traceback:")
                print(traceback.format_exc())
            
            return {
                "status": "error",
                "error": error_msg
            }
    
    def execute_multiple_tool_calls(
        self, 
        tool_calls: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Execute multiple tool calls in sequence.
        
        Args:
            tool_calls: List of tool call dictionaries (same format as execute_tool_call)
            
        Returns:
            List of result dictionaries, one for each tool call in order.
            Each result includes:
                - tool_call_id: The ID from the original tool call
                - function_name: The name of the function that was executed
                - result: The result dictionary from the function execution
                
        Example:
            >>> executor.execute_multiple_tool_calls([
            ...     {'id': '1', 'function': {'name': 'create_file', 'arguments': {...}}},
            ...     {'id': '2', 'function': {'name': 'read_file', 'arguments': {...}}}
            ... ])
            [
                {'tool_call_id': '1', 'function_name': 'create_file', 'result': {...}},
                {'tool_call_id': '2', 'function_name': 'read_file', 'result': {...}}
            ]
        """
        self._log(f"Executing {len(tool_calls)} tool calls")
        
        results = []
        for i, tool_call in enumerate(tool_calls):
            self._log(f"--- Tool call {i+1}/{len(tool_calls)} ---")
            
            result = self.execute_tool_call(tool_call)
            
            results.append({
                "tool_call_id": tool_call.get("id"),
                "function_name": tool_call.get("function", {}).get("name"),
                "result": result
            })
        
        self._log(f"Completed all {len(tool_calls)} tool calls")
        return results
    
    def get_available_functions(self) -> List[str]:
        """
        Get list of all available function names.
        
        Returns:
            List of function names
        """
        return list(self.functions.keys())
    
    def get_function_schema(self, function_name: str) -> Optional[Dict[str, Any]]:
        """
        Get the schema for a specific function.
        
        Args:
            function_name: Name of the function
            
        Returns:
            Schema dictionary or None if not found
        """
        return next(
            (t for t in self.tool_schema if t["function"]["name"] == function_name),
            None
        )