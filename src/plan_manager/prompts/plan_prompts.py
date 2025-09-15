from mcp.server.fastmcp.prompts import base


def build_create_plan_prompt_messages() -> list[base.Message]:
    """Few-shot prompt to draft a new Plan (epic-level) for creation.

    Output format aligns with the create_plan tool: title (required),
    description (optional), priority (optional int 0..5).
    """

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
            "Save this JSON in a temporary file named 'plan.json' in a directory called 'todo/temp'. "
            "Create the directories if they don't exist; overwrite the file if it already exists. Then STOP. Do not do anything else. "
            "I might review the JSON, edit it, or ask you to edit it. The review is considered complete when I say 'approve'. "
            "Once I approve, you will create the plan by calling the `create_plan` tool of the Plan Manager MCP server using the fields from the JSON. "
            "Once you have created the plan, you will delete the temporary file."
        ),
    ]
