import logging
from typing import Any, Optional

from pydantic import ValidationError

from plan_manager.domain.models import Plan, Status
from plan_manager.logging_context import get_correlation_id
from plan_manager.services import plan_repository as repo
from plan_manager.services.shared import ensure_unique_id_from_set, generate_slug
from plan_manager.validation import validate_description, validate_title

logger = logging.getLogger(__name__)


def create_plan(
    title: str, description: Optional[str], priority: Optional[int]
) -> dict[str, Any]:
    # Validate inputs
    title = validate_title(title)
    description = validate_description(description)

    plan_id = generate_slug(title)
    logger.info(
        {
            "event": "create_plan",
            "id": plan_id,
            "title": title,
            "corr_id": get_correlation_id(),
        }
    )
    # Ensure not already exists in index (append -2, -3 on collision)
    existing_ids: set[str] = {str(p["id"]) for p in repo.list_plans() if p.get("id")}
    plan_id = ensure_unique_id_from_set(plan_id, existing_ids)

    try:
        plan = Plan(id=plan_id, title=title, description=description, priority=priority)
    except ValidationError as e:
        logger.exception(f"Validation error creating plan '{plan_id}': {e}")
        raise ValueError(f"Validation error creating plan '{plan_id}': {e}") from e

    repo.save(plan, plan_id)
    return plan.model_dump(mode="json", exclude_none=True)


def get_plan(plan_id: str) -> dict[str, Any]:
    plan = repo.load(plan_id)
    return plan.model_dump(mode="json", exclude_none=True)


def update_plan(
    plan_id: str,
    title: Optional[str],
    description: Optional[str],
    priority: Optional[int],
    status: Optional[Status],
) -> dict[str, Any]:
    plan = repo.load(plan_id)
    if title is not None:
        plan.title = title
    if description is not None:
        plan.description = description
    if priority is not None:
        plan.priority = priority
    if status is not None:
        plan.status = status
    repo.save(plan, plan_id)
    return plan.model_dump(mode="json", exclude_none=True)


def delete_plan(plan_id: str) -> dict[str, Any]:
    repo.delete(plan_id)
    return {"success": True, "message": f"Successfully deleted plan '{plan_id}'."}


def list_plans(statuses: Optional[list[Status]] = None) -> list[dict[str, Any]]:
    items = repo.list_plans()
    if statuses:
        allowed = {s.value if hasattr(s, "value") else s for s in statuses}
        items = [p for p in items if p.get("status") in allowed]
    # Sort by priority asc (None last), creation_time asc (string ISO ok), id asc

    def prio_key(v: dict[str, Any]) -> int:
        p = v.get("priority")
        return p if isinstance(p, int) else 6

    def ctime_key(v: dict[str, Any]) -> tuple[bool, str]:
        ct = v.get("creation_time")
        return (ct is None, ct if isinstance(ct, str) else "9999")

    items.sort(key=lambda v: (prio_key(v), ctime_key(v), v.get("id", "")))
    return items
