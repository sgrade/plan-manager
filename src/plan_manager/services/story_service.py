# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import logging
from typing import Any

from pydantic import ValidationError

from plan_manager.domain.models import Plan, Status, Story
from plan_manager.logging_context import get_correlation_id
from plan_manager.services.shared import (
    ensure_plan_exists,
    ensure_story_in_plan,
    find_dependents,
    generate_slug,
    service_uow,
    story_to_dict,
)
from plan_manager.storage import repositories
from plan_manager.validation import (
    validate_acceptance_criteria,
    validate_description,
    validate_title,
)

logger = logging.getLogger(__name__)


def create_story(
    plan_id: str,
    title: str,
    description: str | None,
    acceptance_criteria: list[str] | None,
    priority: int | None,
    depends_on: list[str],
) -> dict[str, Any]:
    # Validate inputs
    title = validate_title(title)
    description = validate_description(description)
    acceptance_criteria = validate_acceptance_criteria(acceptance_criteria)

    generated_id = generate_slug(title)
    logger.info(
        {
            "event": "create_story",
            "title": title,
            "corr_id": get_correlation_id(),
        }
    )
    try:
        new_story = Story(
            id=generated_id,
            title=title,
            description=description,
            acceptance_criteria=acceptance_criteria,
            depends_on=depends_on or [],
            priority=priority,
        )
    except ValidationError as e:
        logger.exception("Validation error creating new story '%s'", generated_id)
        raise ValueError(
            f"Validation error creating new story '{generated_id}': {e}"
        ) from e

    with service_uow(write=True, operation="create_story", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        generated_id = repositories.create_story(
            conn,
            plan_id=plan_id,
            base_id=new_story.id,
            title=new_story.title,
            description=new_story.description,
            status=new_story.status,
            priority=new_story.priority,
            acceptance_criteria=new_story.acceptance_criteria,
            depends_on=new_story.depends_on,
            ord_value=len(repositories.list_stories(conn, plan_id)),
        )
        created = repositories.get_story(conn, plan_id, generated_id)
    if created is None:
        raise RuntimeError(f"Story '{generated_id}' was not persisted.")
    payload = story_to_dict(created)
    payload["plan_id"] = plan_id
    return {
        key: value
        for key, value in payload.items()
        if key
        in {
            "plan_id",
            "id",
            "title",
            "description",
            "acceptance_criteria",
            "priority",
            "depends_on",
            "status",
            "creation_time",
        }
        and value is not None
    }


def get_story(plan_id: str, story_id: str) -> dict[str, Any]:
    with service_uow(write=False, operation="get_story", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        ensure_story_in_plan(conn, plan_id, story_id, parameter_name="story_id")
        story = repositories.get_story(conn, plan_id, story_id)
    if story is None:
        raise KeyError(f"story with ID '{story_id}' not found.")
    payload = story_to_dict(story)
    payload["plan_id"] = plan_id
    return payload


# Note: The status of a Story is a calculated property based on the
# statuses of its Tasks. It is not set directly and is therefore not a
# parameter in this function. The status rollup is handled by the task_service.
def update_story(
    plan_id: str,
    story_id: str,
    title: str | None = None,
    description: str | None = None,
    acceptance_criteria: list[str] | None = None,
    priority: int | None = None,
    depends_on: list[str] | None = None,
) -> dict[str, Any]:
    logger.info(
        {
            "event": "update_story",
            "id": story_id,
            "corr_id": get_correlation_id(),
        }
    )
    with service_uow(write=True, operation="update_story", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        ensure_story_in_plan(conn, plan_id, story_id, parameter_name="story_id")
        current_story = repositories.get_story(conn, plan_id, story_id)
        if current_story is None:
            raise KeyError(f"story with ID '{story_id}' not found.")
        repositories.update_story(
            conn,
            plan_id=plan_id,
            story_id=story_id,
            title=title if title is not None else repositories.UNSET,
            description=description if description is not None else repositories.UNSET,
            acceptance_criteria=(
                acceptance_criteria
                if acceptance_criteria is not None
                else repositories.UNSET
            ),
            depends_on=depends_on if depends_on is not None else repositories.UNSET,
            priority=priority if priority is not None else repositories.UNSET,
        )
        updated_story = repositories.get_story(conn, plan_id, story_id)
    if updated_story is None:
        raise RuntimeError(f"Story '{story_id}' disappeared during update.")
    payload = story_to_dict(updated_story)
    payload["plan_id"] = plan_id
    return payload


def delete_story(plan_id: str, story_id: str) -> dict[str, Any]:
    logger.info(
        {
            "event": "delete_story",
            "id": story_id,
            "corr_id": get_correlation_id(),
        }
    )
    with service_uow(write=True, operation="delete_story", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        ensure_story_in_plan(conn, plan_id, story_id, parameter_name="story_id")
        plan_row = repositories.get_plan(conn, plan_id)
        if plan_row is None:
            raise FileNotFoundError(f"Plan '{plan_id}' not found.")
        stories = repositories.list_stories(conn, plan_id)
        by_story_id = {story.id: story for story in stories}
        if story_id not in by_story_id:
            raise KeyError(f"story with ID '{story_id}' not found.")
        tasks = repositories.list_tasks(conn, plan_id)
        tasks_by_story: dict[str, list[Any]] = {}
        for task in tasks:
            tasks_by_story.setdefault(task.story_id or "", []).append(task)
        plan_snapshot = Plan(
            id=plan_id,
            title=plan_row.title,
            stories=[
                Story(
                    id=story.id,
                    title=story.title,
                    description=story.description,
                    status=story.status,
                    priority=story.priority,
                    acceptance_criteria=story.acceptance_criteria,
                    depends_on=story.depends_on,
                    creation_time=story.creation_time,
                    completion_time=story.completion_time,
                    tasks=tasks_by_story.get(story.id, []),
                )
                for story in stories
            ],
        )
        deps = find_dependents(plan_snapshot, story_id)
        if deps:
            dep_list = ", ".join(deps)
            raise ValueError(
                f"Cannot delete story '{story_id}' because it is a dependency of: {dep_list}"
            )
        repositories.delete_story(conn, plan_id, story_id)
    return {"success": True, "message": f"Successfully deleted story '{story_id}'."}


def list_stories(
    plan_id: str,
    statuses: list[Status] | None,
    unblocked: bool = False,
) -> list[Story]:
    """Return domain stories after topological sort and filtering.

    - Topo sorts by dependencies (Kahn's algorithm).
    - Within each ready set, sorts by priority asc (None last),
      creation_time asc (None last), id asc.
    - Filters by allowed statuses if provided.
    - If unblocked=True, includes only TODO stories whose dependencies are all DONE.
    """
    with service_uow(write=False, operation="list_stories", plan_id=plan_id) as conn:
        ensure_plan_exists(conn, plan_id)
        return repositories.list_stories(
            conn,
            plan_id,
            statuses=statuses,
            unblocked=unblocked,
        )
