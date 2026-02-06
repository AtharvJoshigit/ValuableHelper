from abc import ABC, abstractmethod
from typing import Any, Dict
from pydantic import BaseModel, Field
from copy import deepcopy


class BaseTool(BaseModel, ABC):
    """
    Abstract base class for all tools in the framework.
    Uses Pydantic for validation and schema generation.
    """
    name: str = Field(..., description="The name of the tool")
    description: str = Field(..., description="A description of what the tool does")

    class Config:
        arbitrary_types_allowed = True

    @abstractmethod
    def execute(self, **kwargs) -> Any:
        """
        Execute the tool logic.
        
        Args:
            **kwargs: The arguments for the tool execution.
            
        Returns:
            The result of the tool execution.
        """
        pass

    def get_schema(self) -> Dict[str, Any]:
        """
        Get the JSON schema for the tool arguments.
        Excludes 'name' and 'description' from the properties as they are metadata.
        """
        schema = deepcopy(self.model_json_schema())
        
        # Remove metadata fields
        metadata_fields = ["name", "description"]
        properties = schema.get("properties", {})
        for field in metadata_fields:
            properties.pop(field, None)
        
        # Clean up required list
        required = schema.get("required", [])
        schema["required"] = [r for r in required if r not in metadata_fields]
        
        if not schema.get("required"):
            schema.pop("required", None)
        
        return schema
