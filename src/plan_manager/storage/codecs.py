# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Shared SQLite codecs for storage repositories and importer."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from plan_manager.domain.models import Task


def dumps_json(value: Any) -> str | None:
    """Serialize a JSON payload with stable key ordering."""
    if value is None:
        return None
    return json.dumps(value, sort_keys=True)


def loads_json(value: Any) -> Any:
    """Deserialize JSON payloads stored as TEXT columns."""
    if value is None:
        return None
    return json.loads(str(value))


def serialize_steps(steps: list[Task.Step] | None) -> list[dict[str, Any]] | None:
    """Serialize task steps for JSON storage."""
    if steps is None:
        return None
    return [step.model_dump(mode="json") for step in steps]
