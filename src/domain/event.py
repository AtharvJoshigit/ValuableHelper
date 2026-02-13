
from enum import Enum
from typing import Any, Dict, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class EventType(str, Enum):
    TASK_CREATED = "task_created"
    TASK_UPDATED = "task_updated"
    TASK_STATUS_CHANGED = "task_status_changed"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    TASK_DELETED = "task_deleted"
    PLAN_UPDATED = "plan_updated"
    SYSTEM_STARTUP = "system_startup"
    SYSTEM_SHUTDOWN = "system_shutdown"
    USER_MESSAGE = "user_message"
    USER_APPROVAL = "user_approval"
    HEARTBEAT = "heartbeat"
    TOOL_EXECUTION_STARTED = "tool_execution_started"
    TOOL_EXECUTION_COMPLETED = "tool_execution_completed"
    TOOL_EXECUTION_FAILED = "tool_execution_failed"

class Event(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: EventType
    payload: Dict[str, Any]
    source: str = "system"
    timestamp: datetime = Field(default_factory=datetime.now)
