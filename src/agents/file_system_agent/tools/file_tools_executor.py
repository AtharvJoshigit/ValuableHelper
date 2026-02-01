import json
from typing import Dict, Any, List, Optional, Callable
from src.client.universal_ai_client import UniversalAIClient


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
    def __init__(self, filesystem_functions: Dict[str, Callable]):
        self.functions = filesystem_functions
    
    def execute_tool_call(self, tool_call: Dict[str, Any]) -> Dict[str, Any]:
        function_name = tool_call.get("function", {}).get("name")
        arguments = tool_call.get("function", {}).get("arguments", {})
        
        if isinstance(arguments, str):
            arguments = json.loads(arguments)
        
        if function_name not in self.functions:
            return {
                "status": "error",
                "error": f"Unknown function: {function_name}"
            }
        
        try:
            result = self.functions[function_name](**arguments)
            return result
        except Exception as e:
            return {
                "status": "error",
                "error": f"Error executing {function_name}: {str(e)}"
            }
    
    def execute_multiple_tool_calls(self, tool_calls: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        results = []
        for tool_call in tool_calls:
            result = self.execute_tool_call(tool_call)
            results.append({
                "tool_call_id": tool_call.get("id"),
                "function_name": tool_call.get("function", {}).get("name"),
                "result": result
            })
        return results