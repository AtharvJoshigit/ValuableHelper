from pydantic import BaseModel, ConfigDict, Field
from typing import List, Dict, Any, Literal, Optional
from datetime import datetime, timezone
import uuid

class VectorDocument(BaseModel):
    """Represents a single unit of information to be stored."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str # The text to be embedded (e.g., tool description or memory text)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
class SearchResult(BaseModel):
    """Standardized return object for RAG queries."""
    id: str
    content: str
    metadata: Dict[str, Any]
    score: float # Distance/Similarity score

class ToolSchema(BaseModel):
    """Specific schema for indexing tools."""
    name: str
    id : Optional[str] = None
    purpose: str
    description: str
    version: Optional[str] = '1.0'
    module_path: str
    class_name: str


class MemorySchema(BaseModel):
    agent_id: str
    agent_name: Optional[str] = None
    content: str
    role: str
    summary_type: Optional[Literal["short", "long"]] = None
    importance: int = Field(default=5, ge=1, le=10)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    message_count: Optional[int] = None
    tags: Optional[List[str]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )   