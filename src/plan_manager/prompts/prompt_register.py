from typing import Callable, List, Optional, TypedDict
from mcp.server.fastmcp.prompts import base

from plan_manager.prompts.plan_prompts import build_create_plan_prompt_messages
from plan_manager.prompts.story_prompts import build_create_stories_prompt_messages
from plan_manager.prompts.task_prompts import build_create_tasks_prompt_messages
from plan_manager.prompts.task_prompts import build_create_steps_prompt_messages


class PromptSpec(TypedDict):
    name: str
    title: str
    description: str
    handler: Callable[[Optional[str]], List[base.Message]]


# Catalog of prompts defined in this module. Servers can import this and
# dynamically register/unregister entries at runtime.
PROMPT_SPECS: List[PromptSpec] = [
    {
        "name": "create_plan",
        "title": "Create a plan",
        "description": "Guides the model to create a plan as MAJOR-level change. The plan must have title and description. The plan should be a cohesive scope of work.",
        "handler": build_create_plan_prompt_messages,
    },
    {
        "name": "create_stories",
        "title": "Create stories for a plan",
        "description": "Guides the model to create stories for a plan as MINOR-level changes. Each story must have title, description (user story), and verifiable acceptance criteria.",
        "handler": build_create_stories_prompt_messages,
    },
    {
        "name": "create_tasks",
        "title": "Create tasks for a story",
        "description": "Guides the model to create tasks for a story as PATCH-level changes. Each task must have title and may have a description.",
        "handler": build_create_tasks_prompt_messages,
    },
    {
        "name": "create_steps",
        "title": "Create steps for a task",
        "description": "Guides the model to create implementation steps for a task as PATCH changelog bullet points. Each step must have title and may have a description.",
        "handler": build_create_steps_prompt_messages,
    },
]


def register_prompts(mcp_instance, prompt_specs: Optional[List[PromptSpec]] = None) -> None:
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
