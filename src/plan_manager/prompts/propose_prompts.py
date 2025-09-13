from typing import Callable, List, Optional, TypedDict
from mcp.server.fastmcp.prompts import base

from plan_manager.services.state_repository import (
    get_current_plan_id,
    get_current_story_id,
    get_current_task_id,
)

# --- Prompt Definition (messages builder) ---


def _build_propose_stories_for_plan_prompt_messages(plan_id: Optional[str] = None) -> list[base.Message]:
    """Construct the messages for 'propose_stories_for_plan' using the given plan_id."""

    if not plan_id:
        try:
            plan_id = get_current_plan_id()
        except ValueError as e:
            raise ValueError(
                "Could not determine a plan_id to build the prompt.") from e

    return [
        # == Turn 1: The Example ==
        # This is the "few-shot" example we provide to the model.
        base.UserMessage(
            "You are an AI assistant for agile project management. "
            "Your task is to break down a plan (similar to an epic) into smaller user stories. "
            "Each story should map to a MINOR-level change in semantic versioning. "
            "Respond with a valid JSON array of objects. "
            "Each object must contain exactly three keys: 'title' (string), 'description' (string), and 'acceptance_criteria' (array of strings). "
            "The 'description' represents the user story and must be in the format 'As a [user type], I want [goal], so that [benefit].'. "
            "Do not add any other text or formatting. "
            "\n\nHere is the example epic: User Authentication"
        ),
        base.AssistantMessage(
            """[
  {
    "title": "New User Registration",
    "description": "As a new visitor, I want to create an account using my email and a password, so that I can access personalized features of the platform.",
    "acceptance_criteria": [
    "User can enter an email address and a password.",
    "System validates that the email format is correct.",
    "System enforces password complexity rules.",
    "User receives a confirmation email upon successful registration."
    ]
  },
  {
    "title": "User Login",
    "description": "As a registered user, I want to log in with my credentials, so that I can access my account and saved data.",
    "acceptance_criteria": [
    "User can enter their email and password.",
    "System validates the credentials against stored records.",
    "User is redirected to their dashboard upon successful login.",
    "User sees a clear error message for invalid credentials."
    ]
  }
]"""
        ),

        # == Turn 2: The Real Request ==
        # Now that the model has seen the pattern, we ask our actual question.
        base.UserMessage(
            f"Now, generate user stories for this plan: {plan_id}"
        ),
    ]


def _build_propose_tasks_for_story_prompt_messages(story_id: Optional[str] = None) -> list[base.Message]:
    """Construct the messages for 'propose_tasks_for_story' using the given story_id."""

    if not story_id:
        try:
            story_id = get_current_story_id()
        except ValueError as e:
            raise ValueError(
                "Could not determine a story_id to build the prompt.") from e

    return [
        # == Turn 1: The Example ==
        # This is the "few-shot" example we provide to the model.
        base.UserMessage(
            "You are an AI assistant for agile project management. Break a single user story into clear, developer-ready tasks. "
            "Each task should correspond to a PATCH-level change in semantic versioning. "
            "Respond with a valid JSON array of objects. Each object must contain exactly two keys: 'title' (string) and 'description' (string). "
            "Do not include any other text or formatting. "
            "\n\nHere is the example story: New User Registration"
        ),
        base.AssistantMessage(
            """[
  {
    "title": "Design registration form UI",
    "description": "Create a responsive form with fields for email and password, including client-side validation hints."
  },
  {
    "title": "Implement registration API endpoint",
    "description": "Add a POST /api/auth/register endpoint that validates input, hashes passwords, and creates the user record."
  },
  {
    "title": "Enforce input validation and password policy",
    "description": "Validate email format and enforce password complexity (length, charset); return structured error messages."
  },
  {
    "title": "Send verification email after sign-up",
    "description": "Generate a signed verification token, store it, and send an email with a verification link."
  }
]"""
        ),

        # == Turn 2: The Real Request ==
        # Now that the model has seen the pattern, we ask our actual question.
        base.UserMessage(
            f"Now, generate tasks for this story: {story_id}"
        ),
    ]


def _build_propose_steps_for_task_prompt_messages(task_id: Optional[str] = None) -> list[base.Message]:
    """Construct the messages for 'propose_steps_for_task' using the given task_id."""

    if not task_id:
        try:
            task_id = get_current_task_id()
        except ValueError as e:
            raise ValueError(
                "Could not determine a task_id to build the prompt.") from e

    return [
        # == Turn 1: The Example ==
        # This is the "few-shot" example we provide to the model.
        base.UserMessage(
            "You are an AI assistant for agile project management. Break a single task into concrete implementation steps. "
            "Each step should be a small, self‑contained change appropriate for a single bullet in the next patch release notes (typically under ‘Fixed’ or similar), when user‑visible. "
            "Respond with a valid JSON array of objects. Each object must contain exactly two keys: 'title' (string) and 'description' (string). "
            "Do not include any other text or formatting. "
            "\n\nHere is the example task: Implement registration API endpoint"
        ),
        base.AssistantMessage(
            """[
  {
    "title": "Define endpoint route and method",
    "description": "Add POST /api/auth/register route to the router with handler stub."
  },
  {
    "title": "Validate request body",
    "description": "Validate email format and password policy; return 400 with field errors on failure."
  },
  {
    "title": "Hash password securely",
    "description": "Hash the plaintext password using a strong algorithm and per-user salt."
  },
  {
    "title": "Create user record",
    "description": "Persist the new user with sanitized fields; enforce unique email constraint."
  },
  {
    "title": "Return success response",
    "description": "Return 201 Created with minimal user payload (no sensitive fields)."
  }
]"""
        ),

        # == Turn 2: The Real Request ==
        # Now that the model has seen the pattern, we ask our actual question.
        base.UserMessage(
            f"Now, generate implementation steps for this task: {task_id}"
        ),
    ]


# --- Prompt Catalog ---

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
        "handler": _build_propose_stories_for_plan_prompt_messages,
    },
    {
        "name": "propose_tasks_for_story",
        "title": "Propose tasks for a story",
        "description": "Asks the model to propose tasks for a story. Each task should have title and description.",
        "handler": _build_propose_tasks_for_story_prompt_messages,
    },
    {
        "name": "propose_steps_for_task",
        "title": "Propose steps for a task",
        "description": "Asks the model to propose implementation steps for a task as PATCH changelog bullet points.",
        "handler": _build_propose_steps_for_task_prompt_messages,
    },
]


def register_propose_prompts(mcp_instance, prompt_specs: Optional[List[PromptSpec]] = None) -> None:
    """Register prompts with the MCP instance using provided specs.

    This indirection makes it easy to later support dynamic runtime changes
    (add/remove/update prompt specs) and emit listChanged notifications.
    """
    for spec in (prompt_specs or PROMPT_SPECS):
        # Explicitly create and register the handler to avoid unused function warnings.
        def _make_wrapper(handler: Callable[[Optional[str]], List[base.Message]]):
            def _wrapper(work_item_id: str) -> List[base.Message]:
                return handler(work_item_id)
            return _wrapper

        wrapper = _make_wrapper(spec["handler"])
        mcp_instance.prompt(
            name=spec["name"],
            title=spec["title"],
            description=spec["description"],
        )(wrapper)
