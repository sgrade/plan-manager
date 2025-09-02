"""Transport-facing input schemas for MCP tools.

These Pydantic models define request payloads for tool functions with
per-field descriptions, so MCP clients can display rich parameter help.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from plan_manager.domain.models import Status


# --- Plan Schemas ---

class CreatePlanIn(BaseModel):
    plan_id: str = Field(..., description="Plan ID")
    title: str = Field(..., description="Plan title")
    description: Optional[str] = Field(
        None, description="Optional description")
    priority: Optional[int] = Field(None, description="Priority 0..5 or None")


class GetPlanIn(BaseModel):
    plan_id: str = Field(..., description="Plan ID")


class UpdatePlanIn(BaseModel):
    plan_id: str = Field(..., description="Plan ID")
    title: Optional[str] = Field(None, description="New title")
    description: Optional[str] = Field(
        None, description="New description (None to clear)")
    priority: Optional[int] = Field(
        None, description="New priority 0..5 or None")
    status: Optional[Status] = Field(None, description="New status")


class DeletePlanIn(BaseModel):
    plan_id: str = Field(..., description="Plan ID")


class ListPlansIn(BaseModel):
    statuses: Optional[List[Status]] = Field(
        None, description="Optional set of statuses to include")


class SetCurrentPlanIn(BaseModel):
    plan_id: str = Field(..., description="Plan ID to set as current")


# --- Story Schemas ---

class CreateStoryIn(BaseModel):
    title: str = Field(..., description="Story title")
    priority: Optional[int] = Field(None, description="Priority 0..5 or None")
    depends_on: List[str] = Field(
        default_factory=list, description="Story IDs this story depends on")
    description: Optional[str] = Field(
        None, description="Optional freeform description")


class GetStoryIn(BaseModel):
    story_id: str = Field(..., description="Story ID")


class UpdateStoryIn(BaseModel):
    story_id: str = Field(..., description="Story ID")
    title: Optional[str] = Field(None, description="New title")
    description: Optional[str] = Field(
        None, description="New description (None to clear)")
    depends_on: Optional[List[str]] = Field(
        None, description="New dependency list")
    priority: Optional[int] = Field(
        None, description="New priority 0..5 or None")
    status: Optional[Status] = Field(None, description="New status")


class DeleteStoryIn(BaseModel):
    story_id: str = Field(..., description="Story ID")


class ListStoriesIn(BaseModel):
    statuses: Optional[List[Status]] = Field(
        None, description="Optional set of statuses to include")
    unblocked: bool = Field(
        False, description="If true, only TODO stories whose dependencies are DONE")


class CreateTaskIn(BaseModel):
    story_id: str = Field(..., description="Parent story ID")
    title: str = Field(..., description="Task title")
    priority: Optional[int] = Field(None, description="Priority 0..5 or None")
    depends_on: List[str] = Field(
        default_factory=list, description="Story or task IDs this task depends on")
    description: Optional[str] = Field(
        None, description="Optional freeform description")


# --- Task Schemas ---

class GetTaskIn(BaseModel):
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")


class UpdateTaskIn(BaseModel):
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


class DeleteTaskIn(BaseModel):
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")


class ListTasksIn(BaseModel):
    statuses: Optional[List[Status]] = Field(
        None, description="Optional set of statuses to filter")
    story_id: Optional[str] = Field(None, description="Optional story filter")


class ExplainTaskBlockersIn(BaseModel):
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")
