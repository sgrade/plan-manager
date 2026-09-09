# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from mcp.server.fastmcp.prompts import base

from plan_manager.prompts.artifact_paths import (
    authority_instructions,
    prompt_artifact_path,
)


def create_tasks_messages(plan_id: str, story_id: str) -> list[base.Message]:
    """Construct the messages for 'create_tasks' prompt using the given story_id."""

    artifact_path = prompt_artifact_path("tasks.json")
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
            f"Now, generate tasks for this story: {story_id} in plan {plan_id}. "
            f"Save this JSON to the new invocation-owned path '{artifact_path}'. "
            "Create its parent directory and do not overwrite any existing file. "
            f"The creation action is `create_task(plan_id='{plan_id}', "
            f"story_id='{story_id}', ...)` using the most recent proposal. "
            + authority_instructions("task creation", artifact_path)
        ),
    ]


def create_steps_messages(plan_id: str, task_id: str) -> list[base.Message]:
    """Construct the messages for 'create_steps' prompt using the given task_id."""

    artifact_path = prompt_artifact_path("steps.json")
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
            f"Now, generate implementation steps for this task: {task_id} in plan {plan_id}. "
            f"Save this JSON to the new invocation-owned path '{artifact_path}'. "
            "Create its parent directory and do not overwrite any existing file. "
            f"The attachment action is `create_task_steps(plan_id='{plan_id}', "
            f"task_id='{task_id}', ...)`, then call "
            f"`start_task(plan_id='{plan_id}', task_id='{task_id}')`. "
            + authority_instructions("step attachment and task start", artifact_path)
        ),
    ]
