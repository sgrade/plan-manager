from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field, field_validator


# Allowed status values for stories
ALLOWED_STATUSES = {"TODO", "IN_PROGRESS", "DONE", "BLOCKED", "DEFERRED"}


class Story(BaseModel):
    id: str
    title: str
    status: str
    details: Optional[str] = None
    depends_on: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = None
    creation_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    priority: Optional[int] = None
    tasks: List['Task'] = Field(default_factory=list)

    @field_validator("status")
    @classmethod
    def status_must_be_allowed(cls, value: str) -> str:
        if value.upper() not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{value}'. Allowed: {', '.join(sorted(list(ALLOWED_STATUSES)))}"
            )
        return value.upper()

    @field_validator("priority")
    @classmethod
    def priority_must_be_in_range(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not (0 <= value <= 5):
            raise ValueError("Priority must be between 0 and 5 (inclusive) if provided.")
        return value

    @field_validator("tasks", mode="before")
    @classmethod
    def coerce_tasks(cls, value):
        # Support legacy formats: list of fully-qualified IDs or list of dicts
        if value is None:
            return []
        if isinstance(value, list):
            coerced = []
            for item in value:
                if isinstance(item, str):
                    # Expect 'storyId:taskId' or just 'taskId'
                    if ':' in item:
                        sid, lid = item.split(':', 1)
                    else:
                        sid, lid = None, item
                    coerced.append({
                        'id': f"{sid}:{lid}" if sid else lid,
                        'title': lid.replace('_', ' '),
                        'status': 'TODO',
                        'story_id': sid,
                    })
                elif isinstance(item, dict):
                    coerced.append(item)
                else:
                    # Already a Task or unknown; let pydantic try to coerce
                    coerced.append(item)
            return coerced
        return value


# Phase 1: Introduce a base WorkItem and Task model (not yet wired into Story)
class WorkItem(BaseModel):
    id: str
    title: str
    status: str
    depends_on: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = None
    creation_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    priority: Optional[int] = None

    @field_validator("status")
    @classmethod
    def status_must_be_allowed(cls, value: str) -> str:
        if value.upper() not in ALLOWED_STATUSES:
            raise ValueError(
                f"Invalid status '{value}'. Allowed: {', '.join(sorted(list(ALLOWED_STATUSES)))}"
            )
        return value.upper()

    @field_validator("priority")
    @classmethod
    def priority_must_be_in_range(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not (0 <= value <= 5):
            raise ValueError("Priority must be between 0 and 5 (inclusive) if provided.")
        return value


class Task(WorkItem):
    # Optional fields that will be helpful when we add file mirroring and linkage
    details: Optional[str] = None
    story_id: Optional[str] = None


# Pydantic forward refs
Story.model_rebuild()
