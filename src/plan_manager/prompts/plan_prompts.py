# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from mcp.server.fastmcp.prompts import base

from plan_manager.prompts.artifact_paths import (
    authority_instructions,
    prompt_artifact_path,
)


def build_create_plan_prompt_messages() -> list[base.Message]:
    """Few-shot prompt to draft a new Plan (epic-level) for creation.

    Output format aligns with the create_plan tool: title (required),
    description (optional), priority (optional int 0..5).
    """

    artifact_path = prompt_artifact_path("plan.json")
    return [
        # == Turn 1: The Example ==
        # This is the "few-shot" example we provide to the model.
        base.UserMessage(
            "You are an AI assistant for agile project management. "
            "Draft a new plan (similar to an epic) that describes a cohesive scope of work. "
            "Respond with a valid JSON object. "
            "It must contain the key 'title' (string) and 'description' (string)"
            "The 'description' should concisely explain the scope and intended outcomes. "
            "Do not add any other text or formatting. "
            "\n\nHere is an example plan:"
        ),
        base.AssistantMessage(
            """{
  "title": "User Authentication",
  "description": "Deliver account registration, login, email verification, password reset, and session management to secure access.",
  "priority": 2
}"""
        ),
        # == Turn 2: The Real Request ==
        # Now that the model has seen the pattern, we ask our actual question.
        base.UserMessage(
            "Now, draft a plan for this project. "
            f"Save this JSON to the new invocation-owned path '{artifact_path}'. "
            "Create its parent directory and do not overwrite any existing file. "
            "The creation action is `create_plan` using the JSON fields. "
            + authority_instructions("plan creation", artifact_path)
        ),
    ]
