# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from typing import TYPE_CHECKING

from plan_manager.schemas.outputs import (
    CurrentContextOut,
)
from plan_manager.services.shared import (
    get_current_story_id,
    get_current_task_id,
)

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_context_tools(mcp_instance: "FastMCP") -> None:
    """Register context tools with the MCP instance."""
    mcp_instance.tool()(get_current)


def get_current(plan_id: str) -> CurrentContextOut:
    """Get context for a specific plan.

    Args:
        plan_id: Plan identifier, for example `concurrency_stability`.

    Returns the plan ID, current story ID (if any), and current task ID (if any).
    This helps answer "Where am I?" in the plan hierarchy.

    Returns:
        CurrentContextOut: The current context with plan_id, current_story_id, and current_task_id
    """
    return CurrentContextOut(
        plan_id=plan_id,
        current_story_id=get_current_story_id(plan_id),
        current_task_id=get_current_task_id(plan_id),
    )
