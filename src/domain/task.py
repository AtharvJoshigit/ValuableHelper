from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    WAITING_APPROVAL = "waiting_approval"
    APPROVED = "approved"
    DONE = "done"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    WAITING_REVIEW = 'waiting_review'

class TaskPriority(str, Enum):
    SCHEDULED = "scheduled"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"

class Task(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    description: Optional[str] = None
    status: TaskStatus = TaskStatus.TODO
    priority: TaskPriority = TaskPriority.MEDIUM
    
    # Relationships & Metadata
    parent_id: Optional[str] = None
    dependencies: List[str] = Field(default_factory=list) # List of Task IDs
    tags: List[str] = Field(default_factory=list)
    assigned_to: Optional[str] = None
    
    # New Control Fields
    requires_review: bool = Field(default=True, description="Whether this task needs approval from the PlannerAgent after completion")
    review_feedback: Optional[str] = Field(None, description="Feedback from the PlannerAgent if the task was not approved")
    
    # Flexible context for agents
    context: Dict[str, Any] = Field(default_factory=dict)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    
    result_summary: Optional[str] = None
