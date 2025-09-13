"""Minimal workflow prompts for convenience only.

These prompts provide small, composable templates to assist the user in
authoring execution_intent, execution_summary, and review checklists.

Design constraints:
- No storage coupling. Purely text templates.
- Consume context via parameters only. No server-side state.
- Keep content small and skimmable; the client may prefill and edit.
"""

from typing import List

from mcp.server.fastmcp.prompts.base import AssistantMessage, UserMessage


async def prompt_review_story_proposals_checklist() -> List:
    """Provides a static checklist for reviewing story proposals."""
    return [
        AssistantMessage(
            """
### Story Proposal Review Checklist

**Strategic Alignment**
- [ ] Do these stories, as a whole, fulfill the high-level objective of the parent Plan?
- [ ] Is each story a valuable, user-facing outcome (a "what" and "why")?
- [ ] Does each story represent a meaningful feature or increment (a MINOR change)?

**Quality & Clarity**
- [ ] Are the titles and descriptions clear and unambiguous?
- [ ] Are the stories reasonably independent and vertically sliced?
- [ ] Is anything critical missing from this list to achieve the Plan's goal?
"""
        )
    ]


async def prompt_review_task_proposals_checklist() -> List:
    """Provides a static checklist for reviewing task proposals."""
    return [
        AssistantMessage(
            """
### Task Proposal Review Checklist

**Technical Decomposition**
- [ ] Do these tasks, as a whole, fully cover the technical implementation of the parent Story?
- [ ] Is each task a single, discreet unit of work (a PATCH)?
- [ ] Are the tasks logically sequenced? Are any dependencies missing?

**Clarity for Agent**
- [ ] Are the titles phrased as clear, imperative commands for an agent (e.g., "Implement X," "Create Y")?
- [ ] Is the scope of each task well-defined and unambiguous?
- [ ] Is anything critical missing for an agent to successfully complete the Story?
"""
        )
    ]


async def prompt_propose_steps_for_task(
    task_title: str = "", task_description: str = ""
) -> List:
    return [
        UserMessage(
            f"""
Draft the implementation steps for this task:
- Task: {task_title}
- Description: {task_description}

Include:
1) Objective (what will be accomplished)
2) Scope (what's included and excluded)
3) Acceptance Criteria (how we know it's done)
"""
        ),
        AssistantMessage(
            f"""
**Objective:** {task_description or 'Implement the task as specified'}

**Scope:**
- Implement core functionality
- Add validation and error handling
- Write/adjust tests as needed
- Exclude unrelated refactors or out-of-scope features

**Acceptance Criteria:**
- Meets requirements and passes tests
- No regressions in existing functionality
- Documentation updated if needed
"""
        ),
    ]


async def prompt_execution_summary_template(
    task_title: str = "", files_changed: str = ""
) -> List:
    return [
        UserMessage(
            f"""
Draft an execution_summary for the completed task:
- Task: {task_title}
- Files Changed: {files_changed}

Summarize:
1) What Changed
2) Where (files/components)
3) Impact
"""
        ),
        AssistantMessage(
            f"""
**What Changed:** {task_title or 'Implemented task requirements'}; updated tests and documentation as needed.

**Where:** {files_changed or 'Relevant source and test files'}

**Impact:** Feature works as intended; maintained backward compatibility; improved reliability.
"""
        ),
    ]


async def prompt_review_checklist(
    task_title: str = "", execution_summary: str = ""
) -> List:
    return [
        UserMessage(
            f"""
Create a concise review checklist for:
- Task: {task_title}
- Summary: {execution_summary}
"""
        ),
        AssistantMessage(
            """
**Functionality**
- [ ] Matches proposed steps
- [ ] Acceptance criteria met

**Quality**
- [ ] Style and conventions followed
- [ ] Clear structure; no obvious smells

**Testing**
- [ ] Tests updated/added
- [ ] All tests passing

**Docs & Changelog**
- [ ] Docs updated if needed
- [ ] Execution summary clear
"""
        ),
    ]


async def prompt_agent_usage_guide() -> List:
    return [
        AssistantMessage(
            """
Plan-Manager: AI Agent Usage Guide

**Core Philosophy: The User is in Control**
Your role is to execute simple, explicit commands. Do not chain commands or assume the next step. Present the output to the user and await their next instruction.

**1. Understand Your Context**
- **`get_current`**: Shows your current plan, story, and task focus. Run this if you are unsure of the context.
- **`report`**: Provides a detailed status of the current story and suggests the next logical action. Use `report plan` for a high-level overview.

**2. The Main Workflow: `list` -> `set_current`**
This pattern applies to plans, stories, and tasks.
- **`list_plans` / `list_stories` / `list_tasks`**: Use these to see available items.
- **`set_current_plan <id>` / `set_current_story <id>` / `set_current_task <id>`**: Use these to set your focus.
- **Interactive Mode**: If you don't have an ID, call the `set_current_*` command *without an argument*. The tool will return a list of available items for the user to choose from.

**3. Task Execution Lifecycle**
Once a task is set as current, follow this two-gate approval process:
1.  **Propose Steps**: If a task is in `TODO` and has no steps, the user will ask you to `prepare` it. You will then call **`propose_task_steps`** with a clear implementation plan (objective, scope, etc.).
2.  **First Approval**: The user runs **`approve_task`**. The task moves to `IN_PROGRESS`.
3.  **Implement**: You perform the coding work.
4.  **Submit for Review**: When finished, call **`submit_for_review`** with a summary of your changes. The task moves to `PENDING_REVIEW`.
5.  **Final Approval**: The user runs **`approve_task`** again. The task is marked `DONE`, and the tool returns a changelog snippet.

**Key Commands Cheat Sheet:**
- **Context:** `get_current`, `report`, `report plan`
- **Navigation:** `list_plans`, `set_current_plan`, `list_stories`, `set_current_story`, `list_tasks`, `set_current_task`
- **Creation:** `create_plan`, `create_story`, `create_task`
- **Task Actions:** `propose_task_steps`, `submit_for_review`, `approve_task`
- **Modification:** `update_*`, `delete_*`, `change`
"""
        )
    ]


def register_workflow_prompts(
    mcp_instance,
) -> None:
    """Register minimal workflow prompts on the MCP instance."""

    mcp_instance.prompt(
        name="review_story_proposals_checklist",
        title="Review Story Proposals Checklist",
        description="Provides a checklist to aid in reviewing story proposals.",
    )(prompt_review_story_proposals_checklist)

    mcp_instance.prompt(
        name="review_task_proposals_checklist",
        title="Review Task Proposals Checklist",
        description="Provides a checklist to aid in reviewing task proposals.",
    )(prompt_review_task_proposals_checklist)

    mcp_instance.prompt(
        name="execution_summary_template",
        title="Execution Summary Template",
        description="Template to summarize changes after completing a task",
    )(prompt_execution_summary_template)

    mcp_instance.prompt(
        name="review_checklist",
        title="Review Checklist",
        description="Concise checklist to review before approval",
    )(prompt_review_checklist)

    mcp_instance.prompt(
        name="agent_usage_guide",
        title="Plan-Manager Agent Usage Guide",
        description="Concise instructions for MCP agents to use plan-manager tools",
    )(prompt_agent_usage_guide)
