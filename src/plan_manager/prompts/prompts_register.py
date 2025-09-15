from typing import Callable, List, Optional, TypedDict
from mcp.server.fastmcp.prompts import base

from plan_manager.prompts.story_prompts import build_propose_stories_for_plan_prompt_messages
from plan_manager.prompts.task_prompts import build_propose_tasks_for_story_prompt_messages
from plan_manager.prompts.task_prompts import build_propose_steps_for_task_prompt_messages


class PromptSpec(TypedDict):
    name: str
    title: str
    description: str
    handler: Callable[[Optional[str]], List[base.Message]]


# Catalog of prompts defined in this module. Servers can import this and
# dynamically register/unregister entries at runtime.
PROMPT_SPECS: List[PromptSpec] = [
    {
        "name": "propose_stories_for_plan",
        "title": "Propose stories for a plan",
        "description": "Asks the model to propose stories for a plan. Each story should have title, description (user story), and verifiable acceptance criteria.",
        "handler": build_propose_stories_for_plan_prompt_messages,
    },
    {
        "name": "propose_tasks_for_story",
        "title": "Propose tasks for a story",
        "description": "Asks the model to propose tasks for a story. Each task should have title and description.",
        "handler": build_propose_tasks_for_story_prompt_messages,
    },
    {
        "name": "propose_steps_for_task",
        "title": "Propose steps for a task",
        "description": "Asks the model to propose implementation steps for a task as PATCH changelog bullet points.",
        "handler": build_propose_steps_for_task_prompt_messages,
    },
]


def register_propose_prompts(mcp_instance, prompt_specs: Optional[List[PromptSpec]] = None) -> None:
    """Register prompts with the MCP instance using provided specs.

    This indirection makes it easy to later support dynamic runtime changes
    (add/remove/update prompt specs) and emit listChanged notifications.
    """
    for spec in (prompt_specs or PROMPT_SPECS):
        # Register the real handler directly so FastMCP reflects the actual
        # parameter name (plan_id/story_id/task_id) in the UI.
        mcp_instance.prompt(
            name=spec["name"],
            title=spec["title"],
            description=spec["description"],
        )(spec["handler"])
