from typing import Optional
from mcp.server.fastmcp.prompts import base

from plan_manager.services.state_repository import (
    get_current_plan_id,
)


def build_create_stories_prompt_messages(plan_id: Optional[str] = None) -> list[base.Message]:
    """Construct the messages for 'create_stories' using the given plan_id."""

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
            f"Now, generate user stories for this plan: {plan_id}. "
            "Save this JSON in a temporary file named 'stories.json' in a directory called 'todo/temp'. Create the directories if they doesn't exist. Then STOP. Do not do anything else. "
            "I might review the JSON, edit it, or ask you to edit it. The review is considered complete when I say 'approve'. "
            "Once I approve, you will create the stories by calling `create_story` tool of the Plan Manager MCP server for each story in the JSON. Use the most recent version of the JSON if it was edited. "
            "Once you have created the stories, you will delete the temporary file."
        ),
    ]
