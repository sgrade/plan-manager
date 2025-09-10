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


# --- Report Schemas ---

class ReportOut(BaseModel):
    """Structured report output returned by MCP tools."""
    report: str

# --- Plan Schemas ---


class PlanOut(BaseModel):
    """Structured plan output returned by MCP tools."""
    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None
    completion_time: Optional[str] = None
    description: Optional[str] = None


class PlanListItem(BaseModel):
    """Compact listing shape for plans."""
    id: str
    title: str
    status: Status
    priority: Optional[int] = None
    creation_time: Optional[str] = None


class CurrentContextOut(BaseModel):
    """Current context output returned by MCP tools."""
    plan_id: Optional[str] = None
    current_story_id: Optional[str] = None
    current_task_id: Optional[str] = None


class WorkflowStatusOut(BaseModel):
    """Workflow status output showing current state and next actions."""
    current_task: Optional[dict] = None
    workflow_state: dict
    compliance: dict
    next_actions: List[str]
    actions: Optional[List[dict]] = None


class ChangelogPreviewOut(BaseModel):
    """Structured changelog preview output."""
    markdown: str


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


class ApproveTaskOut(BaseModel):
    """Output schema for the approve_task command."""
    success: bool
    message: str
    changelog_snippet: Optional[str] = None
