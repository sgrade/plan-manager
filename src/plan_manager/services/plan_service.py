# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import logging
from typing import Any, Optional

from pydantic import ValidationError

from plan_manager.domain.models import Plan, Status
from plan_manager.logging_context import get_correlation_id
from plan_manager.services.shared import (
    CURRENT_PLAN_META_KEY,
    generate_slug,
    plan_to_dict,
    service_uow,
)
from plan_manager.storage import repositories
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
    try:
        plan = Plan(id=plan_id, title=title, description=description, priority=priority)
    except ValidationError as e:
        logger.exception("Validation error creating plan '%s'", plan_id)
        raise ValueError(f"Validation error creating plan '{plan_id}': {e}") from e

    with service_uow(write=True, operation="create_plan") as conn:
        plan_id = repositories.create_plan(
            conn,
            base_id=plan.id,
            title=plan.title,
            description=plan.description,
            status=plan.status,
            priority=plan.priority,
        )
        created_plan = repositories.get_plan(conn, plan_id)
        if created_plan is None:
            raise RuntimeError(f"Plan '{plan_id}' was not persisted.")
        if repositories.get_meta_value(conn, CURRENT_PLAN_META_KEY) is None:
            repositories.set_meta_value(conn, CURRENT_PLAN_META_KEY, plan_id)
    return plan_to_dict(created_plan)


def get_plan(plan_id: str) -> dict[str, Any]:
    with service_uow(write=False, operation="get_plan", plan_id=plan_id) as conn:
        plan = repositories.get_plan(conn, plan_id)
    if plan is None:
        raise FileNotFoundError(f"Plan '{plan_id}' not found.")
    return plan_to_dict(plan)


def update_plan(
    plan_id: str,
    title: Optional[str],
    description: Optional[str],
    priority: Optional[int],
    status: Optional[Status],
) -> dict[str, Any]:
    with service_uow(write=True, operation="update_plan", plan_id=plan_id) as conn:
        current = repositories.get_plan(conn, plan_id)
        if current is None:
            raise FileNotFoundError(f"Plan '{plan_id}' not found.")
        repositories.update_plan(
            conn,
            plan_id=plan_id,
            title=title if title is not None else repositories.UNSET,
            description=description if description is not None else repositories.UNSET,
            priority=priority if priority is not None else repositories.UNSET,
            status=status if status is not None else repositories.UNSET,
        )
        updated = repositories.get_plan(conn, plan_id)
    if updated is None:
        raise RuntimeError(f"Plan '{plan_id}' disappeared during update.")
    return plan_to_dict(updated)


def delete_plan(plan_id: str) -> dict[str, Any]:
    with service_uow(write=True, operation="delete_plan", plan_id=plan_id) as conn:
        deleted = repositories.delete_plan(conn, plan_id)
        if not deleted:
            raise FileNotFoundError(f"Plan '{plan_id}' not found.")
        current = repositories.get_meta_value(conn, CURRENT_PLAN_META_KEY)
        if current == plan_id:
            remaining = repositories.list_plans(conn)
            if remaining:
                repositories.set_meta_value(
                    conn, CURRENT_PLAN_META_KEY, remaining[0].id
                )
            else:
                repositories.delete_meta_value(conn, CURRENT_PLAN_META_KEY)
    return {"success": True, "message": f"Successfully deleted plan '{plan_id}'."}


def list_plans(statuses: Optional[list[Status]] = None) -> list[dict[str, Any]]:
    with service_uow(write=False, operation="list_plans") as conn:
        items = [plan_to_dict(plan) for plan in repositories.list_plans(conn)]
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
