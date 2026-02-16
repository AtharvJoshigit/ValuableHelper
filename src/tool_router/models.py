from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime

class ToolHealthStatus(BaseModel):
    """Real-time status of a tool."""
    tool_name: str
    status: str = Field(..., description="'active', 'degraded', or 'offline'")
    latency_ms: float = 0.0
    last_checked: datetime = Field(default_factory=datetime.utcnow)
    message: Optional[str] = None

class ToolMetadata(BaseModel):
    """Metadata for filtering and permission control."""
    tags: List[str] = Field(default_factory=list, description="e.g., ['finance', 'read-only']")
    min_permission_level: int = Field(default=0, description="0=Public, 1=User, 2=Admin")
    version: str = "1.0.0"
    author: Optional[str] = None

class ToolRegisterRequest(BaseModel):
    """Payload to register a new tool."""
    name: str
    description: str
    args_schema: Dict[str, Any]
    function_call: str = Field(..., description="Python path: module.submodule.function")
    metadata: ToolMetadata = Field(default_factory=ToolMetadata)

class ToolQueryRequest(BaseModel):
    """Agent's search intent."""
    query: str
    limit: int = 5
    required_tags: List[str] = Field(default_factory=list, description="Filter results by tag")
    min_permission_level: int = Field(default=0, description="Filter out tools above this level")

class ToolResponse(BaseModel):
    """Standardized tool definition returned to the agent."""
    name: str
    description: str
    args_schema: Dict[str, Any]
    metadata: ToolMetadata
    health: Optional[ToolHealthStatus] = None
