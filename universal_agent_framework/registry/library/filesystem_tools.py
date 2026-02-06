import os
from typing import Any, Optional
from pydantic import Field
from universal_agent_framework.registry.base_tool import BaseTool

class ListDirectoryTool(BaseTool):
    """
    Tool to list contents of a directory.
    """
    name: str = "list_directory"
    description: str = "List files and directories in a given path. If no path is provided, it lists the current directory."
    path: str = Field(default=".", description="The directory path to list.")

    def execute(self, **kwargs) -> Any:
        path = kwargs.get("path", self.path)
        try:
            items = os.listdir(path)
            return {"items": items, "path": os.path.abspath(path)}
        except Exception as e:
            return {"error": str(e)}

class ReadFileTool(BaseTool):
    """
    Tool to read the contents of a file.
    """
    name: str = "read_file"
    description: str = "Read the contents of a file at the specified path."
    file_path: str = Field(default=".", description="The path to the file to read.")

    def execute(self, **kwargs) -> Any:
        file_path = kwargs.get("file_path")
        if not file_path:
            return {"status": "error", "error": "file_path is required"}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"content": content, "file_path": os.path.abspath(file_path)}
        except Exception as e:
            return {"status": "error", "error": str(e)}

class CreateFileTool(BaseTool):
    """
    Tool to create a new file or overwrite an existing one.
    """
    name: str = "create_file"
    description: str = "Create a new file with the specified content."
    file_path: str = Field(..., description="The path where the file should be created.")
    content: str = Field(..., description="The content to write to the file.")

    def execute(self, **kwargs) -> Any:
        file_path = kwargs.get("file_path")
        if not file_path:
            return {"status": "error", "error": "file_path is required"}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"status": "success", "content": content, "file_path": os.path.abspath(file_path)}
        except FileNotFoundError:
            return {"status": "error", "error": f"File not found: {file_path}"}
        except PermissionError:
            return {"status": "error", "error": f"Permission denied: {file_path}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}
