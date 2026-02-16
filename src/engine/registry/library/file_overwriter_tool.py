import os
from typing import List, Optional
from engine.registry.base_tool import BaseTool
from pydantic import Field

class FileOverwriterTool(BaseTool):
    name: str = "file_overwriter"
    description: str = "Overwrites a file with new content."
    capabilities: List[str] = ["file_io"]
    
    file_path: Optional[str] = Field(default=None, description="Path to file")
    content: Optional[str] = Field(default=None, description="Content to write")

    def execute(self, **kwargs):
        path = kwargs.get('file_path')
        content = kwargs.get('content')
        if not path or content is None:
            return "Error: file_path and content are required."
            
        try:
            with open(path, 'w', encoding='utf-8') as f:
                f.write(content)
            return f"Successfully wrote to {path}"
        except Exception as e:
            return f"Error writing file: {str(e)}"
