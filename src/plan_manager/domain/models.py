import importlib
import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field, ValidationInfo, field_validator, model_validator

logger = logging.getLogger(__name__)


class Status(str, Enum):
    TODO = "TODO"
    IN_PROGRESS = "IN_PROGRESS"
    PENDING_REVIEW = "PENDING_REVIEW"
    DONE = "DONE"
    BLOCKED = "BLOCKED"
    DEFERRED = "DEFERRED"


class WorkItem(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    priority: Optional[int] = None
    depends_on: Optional[list[str]] = Field(default_factory=list)
    status: Status = Field(default=Status.TODO)
    creation_time: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completion_time: Optional[datetime] = None

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
            raise ValueError(
                "Priority must be between 0 and 5 (inclusive) if provided."
            )
        return value


class Story(WorkItem):
    """A Story represents a user-facing outcome (the 'what' and 'why').
    Its 'how' is the collection of tasks it contains."""

    file_path: Optional[str] = None
    acceptance_criteria: Optional[list[str]] = None
    tasks: list["Task"] = Field(default_factory=list)


class Task(WorkItem):
    """A Task represents the implementation steps for an agent (the 'how').
    While a story provides the high-level context, a task also has its own
    granular 'what' (title), 'why' (description), and 'how' (steps)."""

    file_path: Optional[str] = None
    story_id: Optional[str] = None
    local_id: Optional[str] = None
    # See Story fields for semantics
    # Steps are small implementation bullets suitable for PATCH-level changes.

    class Step(BaseModel):
        title: str
        description: Optional[str] = None

    steps: Optional[list[Step]] = Field(
        default_factory=list,
        description="Ordered implementation steps. Each step has a title and an optional description.",
    )
    changelog_entries: list[str] = Field(
        default_factory=list,
        description="List of changelog entries describing what was accomplished (keepachangelog.com format).",
    )

    class ReviewFeedback(BaseModel):
        message: str
        at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
        by: Optional[str] = None

    review_feedback: list[ReviewFeedback] = Field(default_factory=list)
    rework_count: int = Field(default=0)


Story.model_rebuild()


class Plan(WorkItem):
    stories: list[Story] = Field(default_factory=list)

    @model_validator(mode="after")
    def check_dependencies_exist_and_no_cycles(self, info: ValidationInfo) -> "Plan":
        # For now, forbids plan-level dependencies to avoid cross-plan graphs
        if getattr(self, "depends_on", None):
            raise ValueError(
                "Plan.depends_on is not supported; plans cannot depend on other plans. This is intentional."
            )

        if info.context and info.context.get("skip_dependency_check"):
            logger.debug(
                "Skipping dependency check for Plan validation based on context."
            )
            return self
        # Load validation at runtime to avoid import resolution issues
        validation_module = importlib.import_module("plan_manager.domain.validation")
        validation_module.validate_plan_dependencies(self.stories)
        return self
