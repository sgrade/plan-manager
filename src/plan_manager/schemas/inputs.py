"""Transport-facing input schemas for MCP tools.

These Pydantic models define request payloads for tool functions with
per-field descriptions, so MCP clients can display rich parameter help.
"""

from typing import Optional, List
from pydantic import BaseModel, Field
from plan_manager.domain.models import Status


class CreateStoryIn(BaseModel):
    title: str = Field(..., description="Story title")
    priority: Optional[int] = Field(None, description="Priority 0..5 or None")
    depends_on: List[str] = Field(
        default_factory=list, description="Story IDs this story depends on")
    notes: Optional[str] = Field(None, description="Optional freeform notes")


class UpdateStoryIn(BaseModel):
    story_id: str = Field(..., description="Story ID")
    title: Optional[str] = Field(None, description="New title")
    notes: Optional[str] = Field(None, description="New notes (None to clear)")
    depends_on: Optional[List[str]] = Field(
        None, description="New dependency list")
    priority: Optional[int] = Field(
        None, description="New priority 0..5 or None")
    status: Optional[Status] = Field(None, description="New status")


class GetStoryIn(BaseModel):
    story_id: str = Field(..., description="Story ID")


class DeleteStoryIn(BaseModel):
    story_id: str = Field(..., description="Story ID")


class CreateTaskIn(BaseModel):
    story_id: str = Field(..., description="Parent story ID")
    title: str = Field(..., description="Task title")
    priority: Optional[int] = Field(None, description="Priority 0..5 or None")
    depends_on: List[str] = Field(
        default_factory=list, description="Story or task IDs this task depends on")
    notes: Optional[str] = Field(None, description="Optional freeform notes")


class UpdateTaskIn(BaseModel):
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")
    title: Optional[str] = Field(None, description="New title")
    notes: Optional[str] = Field(None, description="New notes (None to clear)")
    depends_on: Optional[List[str]] = Field(
        None, description="New dependency list (story or task IDs)")
    priority: Optional[int] = Field(
        None, description="New priority 0..5 or None")
    status: Optional[Status] = Field(None, description="New status")


class GetTaskIn(BaseModel):
    story_id: str = Field(..., description="Parent story ID")
    task_id: str = Field(..., description="Local task ID or FQ ID")


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


class ListStoriesIn(BaseModel):
    statuses: Optional[List[Status]] = Field(
        None, description="Optional set of statuses to include")
    unblocked: bool = Field(
        False, description="If true, only TODO stories whose dependencies are DONE")
