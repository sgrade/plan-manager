"""Transport-facing input schemas for MCP tools.

These Pydantic models define request payloads for tool functions with
per-field descriptions, so MCP clients can display rich parameter help.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from plan_manager.domain.models import Status


# --- Plan Schemas ---

class CreatePlanIn(BaseModel):
    """Structured input for creating a plan."""
    title: str = Field(..., description="Plan title")
    description: Optional[str] = Field(
        None, description="Optional description")
    priority: Optional[int] = Field(None, description="Priority 0..5 or None")


class GetPlanIn(BaseModel):
    """Structured input for getting a plan."""
    plan_id: str = Field(..., description="Plan ID")


class UpdatePlanIn(BaseModel):
    """Structured input for updating a plan."""
    plan_id: str = Field(..., description="Plan ID")
    title: Optional[str] = Field(None, description="New title")
    description: Optional[str] = Field(
        None, description="New description (None to clear)")
    priority: Optional[int] = Field(
        None, description="New priority 0..5 or None")
    status: Optional[Status] = Field(None, description="New status")


class DeletePlanIn(BaseModel):
    """Structured input for deleting a plan."""
    plan_id: str = Field(..., description="Plan ID")


class ListPlansIn(BaseModel):
    """Structured input for listing plans."""
    statuses: Optional[List[Status]] = Field(
        None, description="Optional set of statuses to include")
    offset: Optional[int] = Field(
        0, description="Zero-based offset for pagination")
    limit: Optional[int] = Field(
        None, description="Max number of items to return")


class SetCurrentPlanIn(BaseModel):
    """Structured input for setting the current plan."""
    plan_id: str = Field(..., description="Plan ID to set as current")


class SetCurrentStoryIn(BaseModel):
    """Structured input for setting the current story."""
    story_id: str = Field(...,
                          description="Story ID to set as current in the current plan")


class SetCurrentTaskIn(BaseModel):
    """Structured input for setting the current task."""
    task_id: str = Field(
        ..., description="Task ID (local or FQ) to set as current in the current plan")


# --- Story Schemas ---

class CreateStoryIn(BaseModel):
    """Structured input for creating a story."""
    title: str = Field(..., description="Story title")
    priority: Optional[int] = Field(None, description="Priority 0..5 or None")
    depends_on: List[str] = Field(
        default_factory=list, description="Story IDs this story depends on")
    description: Optional[str] = Field(
        None, description="Optional freeform description")


class GetStoryIn(BaseModel):
    """Structured input for getting a story."""
    story_id: str = Field(..., description="Story ID")


class UpdateStoryIn(BaseModel):
    """Structured input for updating a story."""
    story_id: str = Field(..., description="Story ID")
    title: Optional[str] = Field(None, description="New title")
    description: Optional[str] = Field(
        None, description="New description (None to clear)")
    depends_on: Optional[List[str]] = Field(
        None, description="New dependency list")
    priority: Optional[int] = Field(
        None, description="New priority 0..5 or None")
    status: Optional[Status] = Field(None, description="New status")
    execution_summary: Optional[str] = Field(
        None, description="Brief outcome summary after completion (what changed, where)")


class DeleteStoryIn(BaseModel):
    """Structured input for deleting a story."""
    story_id: str = Field(..., description="Story ID")


class ListStoriesIn(BaseModel):
    """Structured input for listing stories."""
    statuses: Optional[List[Status]] = Field(
        None, description="Optional set of statuses to include")
    unblocked: bool = Field(
        False, description="If true, only TODO stories whose dependencies are DONE")
    offset: Optional[int] = Field(
        0, description="Zero-based offset for pagination")
    limit: Optional[int] = Field(
        None, description="Max number of items to return")


# --- Task Schemas ---

class CreateTaskIn(BaseModel):
    """Structured input for creating a task."""
    story_id: str = Field(..., description="Parent story ID")
    title: str = Field(..., description="Task title")
    priority: Optional[int] = Field(None, description="Priority 0..5 or None")
    depends_on: List[str] = Field(
        default_factory=list, description="Story or task IDs this task depends on")
    description: Optional[str] = Field(
        None, description="Optional freeform description")


class GetTaskIn(BaseModel):
    """Structured input for getting a task."""
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")


class UpdateTaskIn(BaseModel):
    """Structured input for updating a task."""
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")
    title: Optional[str] = Field(None, description="New title")
    description: Optional[str] = Field(
        None, description="New description (None to clear)")
    depends_on: Optional[List[str]] = Field(
        None, description="New dependency list (story or task IDs)")
    priority: Optional[int] = Field(
        None, description="New priority 0..5 or None")
    status: Optional[Status] = Field(None, description="New status")
    execution_summary: Optional[str] = Field(
        None, description="Brief outcome summary after completion (what changed, where)")


class DeleteTaskIn(BaseModel):
    """Structured input for deleting a task."""
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")


class ListTasksIn(BaseModel):
    """Structured input for listing tasks."""
    statuses: Optional[List[Status]] = Field(
        None, description="Optional set of statuses to filter")
    story_id: Optional[str] = Field(None, description="Optional story filter")
    offset: Optional[int] = Field(
        0, description="Zero-based offset for pagination")
    limit: Optional[int] = Field(
        None, description="Max number of items to return")


class ExplainTaskBlockersIn(BaseModel):
    """Structured input for explaining task blockers."""
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")


class SubmitForReviewIn(BaseModel):
    """Structured input for submitting a task for code review."""
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")
    summary: str = Field(...,
                         description="The execution summary for the code review.")


class ProposeStepsIn(BaseModel):
    """Structured input for proposing an implementation plan for a task."""
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")
    plan: str = Field(..., description="The implementation plan for the task.")


# --- Approval Schemas ---

class RequestApprovalIn(BaseModel):
    """Request approval for a story or task before progressing.

    item_id may be omitted to default to the current story/task.
    """
    item_type: str = Field(..., description="'story' or 'task'")
    item_id: Optional[str] = Field(
        None, description="If omitted, defaults to current story/task")
    execution_intent: str = Field(...,
                                  description="Brief how/now plan for this iteration")


class ApproveItemIn(BaseModel):
    """Approve or reject a story or task for progress.

    item_id may be omitted to default to the current story/task.
    """
    item_type: str = Field(..., description="'story' or 'task'")
    item_id: Optional[str] = Field(
        None, description="If omitted, defaults to current story/task")
    approved: bool = Field(...,
                           description="Approve or reject the item for progress")
    notes: Optional[str] = Field(None, description="Optional reviewer notes")


# --- Changelog Schemas ---

class PreviewChangelogIn(BaseModel):
    """Preview a changelog snippet generated from recent activity."""
    version: Optional[str] = Field(
        None, description="Optional version header, e.g., 0.1.0")
    date: Optional[str] = Field(
        None, description="Optional date (YYYY-MM-DD). Defaults to today.")


class GenerateChangelogIn(BaseModel):
    """Generate a changelog snippet (same as preview, returned as markdown)."""
    version: Optional[str] = Field(
        None, description="Optional version header, e.g., 0.1.0")
    date: Optional[str] = Field(
        None, description="Optional date (YYYY-MM-DD). Defaults to today.")


class PublishChangelogIn(BaseModel):
    """Append a generated changelog snippet to a file (default CHANGELOG.md)."""
    version: Optional[str] = Field(
        None, description="Optional version header, e.g., 0.1.0")
    date: Optional[str] = Field(
        None, description="Optional date (YYYY-MM-DD). Defaults to today.")
    target_path: Optional[str] = Field(
        'CHANGELOG.md', description="Target file path to append to")
