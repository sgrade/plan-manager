from typing import Optional

from mcp.server.fastmcp.prompts import base

from plan_manager.services.state_repository import (
    get_current_story_id,
    get_current_task_id,
)


def create_tasks_messages(story_id: Optional[str] = None) -> list[base.Message]:
    """Construct the messages for 'create_tasks' prompt using the given story_id."""

    if not story_id:
        try:
            story_id = get_current_story_id()
        except ValueError as e:
            raise ValueError(
                "Could not determine a story_id to build the prompt."
            ) from e

    return [
        # == Turn 1: The Example ==
        # This is the "few-shot" example we provide to the model.
        base.UserMessage(
            "You are an AI assistant for agile project management. "
            "Break a single user story into clear, developer-ready tasks. "
            "Each task should correspond to a PATCH-level change in semantic versioning. "
            "Respond with a valid JSON array of objects. "
            "Each object must contain exactly two keys: 'title' (string) and 'description' (string). "
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
            f"Now, generate tasks for this story: {story_id}. "
            "Save this JSON in a temporary file named 'tasks.json' in a directory called 'todo/temp'. Create the directories if they doesn't exist. Then STOP. Do not do anything else. "
            "I might review the JSON, edit it, or ask you to edit it. The review is considered complete when I say 'approve'. "
            "Once I approve, you will create the tasks by calling `create_task` tool of the Plan Manager MCP server for each task in the JSON. Use the most recent version of the JSON if it was edited. "
            "Once you have created the tasks, you will delete the temporary file."
        ),
    ]


def create_steps_messages(task_id: Optional[str] = None) -> list[base.Message]:
    """Construct the messages for 'create_steps' prompt using the given task_id."""

    if not task_id:
        try:
            task_id = get_current_task_id()
        except ValueError as e:
            raise ValueError(
                "Could not determine a task_id to build the prompt."
            ) from e

    return [
        # == Turn 1: The Example ==
        # This is the "few-shot" example we provide to the model.
        base.UserMessage(
            "You are an AI assistant for agile project management. Break a single task into concrete implementation steps. "
            "Each step should be a small, self-contained change appropriate for a single bullet in the next patch release notes when user-visible. "
            "Respond with a valid JSON array of step objects. Each object MUST include 'title' (string, <= 80 chars). "
            "Optionally include 'description' (string, <= 200 chars) only if the title could be misunderstood. "
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
    "title": "Validate request body"
  },
  {
    "title": "Hash password securely"
  },
  {
    "title": "Create user record",
    "description": "Persist the new user with sanitized fields; enforce unique email constraint."
  },
  {
    "title": "Return success response"
  }
]"""
        ),
        # == Turn 2: The Real Request ==
        # Now that the model has seen the pattern, we ask our actual question.
        base.UserMessage(
            f"Now, generate implementation steps for this task: {task_id}. "
            "Save this JSON in a temporary file named 'steps.json' in a directory called 'todo/temp'. Create the directories if they don't exist; overwrite the file if it already exists. Then STOP. Do not do anything else. "
            "I might review the JSON, edit it, or ask you to edit it. The review is considered complete when I say 'approve'. "
            "Once I approve, you will attach the steps by calling the `create_task_steps` tool of the Plan Manager MCP server for this task, using the most recent version of the JSON if it was edited. "
            "After the steps are created, call `approve_task` to move the task to IN_PROGRESS. "
            "Once you have created the steps, you will delete the temporary file."
        ),
    ]
