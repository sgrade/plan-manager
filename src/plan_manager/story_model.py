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
