"""Transport-facing output schemas for MCP tools.

These Pydantic models define the structured shapes returned by the MCP
tool functions. They intentionally sit outside of the domain models to keep
transport concerns (serialization, stability of output contracts) separate
from core domain entities and rules.
"""
from typing import Optional, List
from pydantic import BaseModel
from plan_manager.domain.models import Status


class OperationResult(BaseModel):
    """Generic result payload for mutation tools (create, update, delete)."""
    success: bool
    message: str


# --- Plan Schemas ---

class PlanOut(BaseModel):
    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    completion_time: Optional[str] = None
    description: Optional[str] = None


class PlanListItem(BaseModel):
    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None


# --- Story Schemas ---

class StoryOut(BaseModel):
    """Structured story output returned by MCP tools.

    Fields mirror the persisted story attributes that are useful to clients
    and are intentionally stable for external consumers.
    """
    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    description: Optional[str] = None
    depends_on: List[str] = []


class StoryListItem(BaseModel):
    """Compact listing shape for stories.

    Optimized for lists and tables; excludes heavy or rarely used fields.
    """
    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    completion_time: Optional[str] = None


# --- Task Schemas ---

class TaskOut(BaseModel):
    """Structured task output returned by MCP tools.

    Includes lifecycle timestamps and dependency list for client UIs and
    automation.
    """
    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    completion_time: Optional[str] = None
    description: Optional[str] = None
    depends_on: List[str] = []


class TaskListItem(BaseModel):
    """Compact listing shape for tasks.

    Optimized for lists and tables; excludes heavy or rarely used fields.
    """
    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None


class TaskBlocker(BaseModel):
    """Represents a single unresolved dependency blocking a task."""
    type: str
    id: str
    status: str
    reason: str


class TaskBlockersOut(BaseModel):
    """Structured explanation of blockers for a given task."""
    id: str
    title: str
    status: str
    blockers: List[TaskBlocker]
    unblocked: bool
