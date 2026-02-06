from enum import Enum
from nt import O_TEMPORARY
from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, ConfigDict


class Role(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"

class ToolCall(BaseModel):
    model_config = ConfigDict(extra='allow')
    id: str
    name: str
    # thought: Optional[bool] = None # for google
    arguments: Dict[str, Any]

class ToolResult(BaseModel):
    model_config = ConfigDict(extra='allow')
    tool_call_id: str
    result: Any
    name: str
    error: Optional[str] = None

class Message(BaseModel):
    model_config = ConfigDict(extra='allow')
    role: Role
    content: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    tool_results: List[ToolResult] = Field(default_factory=list)

class UsageMetadata(BaseModel):
    model_config = ConfigDict(extra='allow')
    input_tokens: int = 0
    output_tokens: Optional[int] = 0
    total_tokens: int = 0

class AgentResponse(BaseModel):
    model_config = ConfigDict(extra='allow')
    content: Optional[str] = None
    tool_calls: List[ToolCall] = Field(default_factory=list)
    usage: Optional[UsageMetadata] = None

class StreamChunk(BaseModel):
    model_config = ConfigDict(extra='allow')
    content: Optional[str] = None
    tool_call: Optional[ToolCall] = None
    usage: Optional[UsageMetadata] = None
    finish_reason: Optional[str] = None
