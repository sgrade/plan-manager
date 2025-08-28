from typing import Optional, List
import logging
import importlib
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo


class Status(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"


class WorkItem(BaseModel):
    id: str
    title: str
    status: Status
    depends_on: Optional[List[str]] = Field(default_factory=list)
    notes: Optional[str] = None
    creation_time: Optional[datetime] = None
    completion_time: Optional[datetime] = None
    priority: Optional[int] = None

    @field_validator("status")
    @classmethod
    def status_must_be_allowed(cls, value: Status | str) -> Status:
        if isinstance(value, Status):
            return value
        upper = value.upper()
        try:
            return Status(upper)
        except Exception as e:
            raise ValueError(
                f"Invalid status '{value}'. Allowed: {', '.join([s.value for s in Status])}"
            ) from e

    @field_validator("priority")
    @classmethod
    def priority_must_be_in_range(cls, value: Optional[int]) -> Optional[int]:
        if value is not None and not (0 <= value <= 5):
            raise ValueError("Priority must be between 0 and 5 (inclusive) if provided.")
        return value


class Story(WorkItem):
    details: Optional[str] = None
    tasks: List['Task'] = Field(default_factory=list)


class Task(WorkItem):
    details: Optional[str] = None
    story_id: Optional[str] = None


Story.model_rebuild()


logger = logging.getLogger(__name__)


class Plan(BaseModel):
    stories: List[Story] = Field(default_factory=list)

    @model_validator(mode='after')
    def check_dependencies_exist_and_no_cycles(self, info: ValidationInfo) -> 'Plan':
        if info.context and info.context.get("skip_dependency_check"):
            logger.debug("Skipping dependency check for Plan validation based on context.")
            return self
        # Load validation at runtime to avoid import resolution issues
        validation_module = importlib.import_module("plan_manager.domain.validation")
        validation_module.validate_plan_dependencies(self.stories)
        return self


