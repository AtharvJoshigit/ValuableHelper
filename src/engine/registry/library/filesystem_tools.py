import os
from typing import Any, Optional
from pydantic import Field
from engine.registry.base_tool import BaseTool

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
    name: str = "create_file"
    description: str = "Create a new file with the specified content."
    file_path: Optional[str] = Field(default=None, description="The path where the file should be created.")
    content: Optional[str] = Field(default=None, description="The content to write to the file.")

    def execute(self, **kwargs) -> Any:
        file_path = kwargs.get("file_path", self.file_path)
        content = kwargs.get("content", self.content)
        
        if not file_path:
            return {"status": "error", "error": "file_path is required"}
        
        try:
            # Create parent directories if they don't exist
            os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
            
            # Write content to file
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "status": "success", 
                "message": f"File created successfully",
                "file_path": os.path.abspath(file_path),
                "bytes_written": len(content.encode('utf-8'))
            }
        except PermissionError:
            return {"status": "error", "error": f"Permission denied: {file_path}"}
        except Exception as e:
            return {"status": "error", "error": str(e)}

class SearchAndReplaceTool(BaseTool):
    """
    Surgically replace text in a file.
    """
    name: str = "str_replace"
    description: str = "Replace a specific string in a file with a new string."
    path: Optional[str] = Field(default=None, description="Path to the file.")
    old_str: Optional[str] = Field(default=None, description="The string to be replaced.")
    new_str: Optional[str] = Field(default=None, description="The replacement string.")

    def execute(self, **kwargs) -> Any:
        path = kwargs.get("path")
        old_str = kwargs.get("old_str")
        new_str = kwargs.get("new_str")
        
        try:
            with open(path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_str not in content:
                return {"status": "error", "error": f"String '{old_str}' not found in file."}
                
            new_content = content.replace(old_str, new_str)
            
            with open(path, 'w', encoding='utf-8') as f:
                f.write(new_content)
                
            return {"status": "success", "message": "String replaced successfully."}
        except Exception as e:
            return {"status": "error", "error": str(e)}
