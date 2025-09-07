"""Minimal workflow prompts for convenience only.

These prompts provide small, composable templates to assist the user in
authoring execution_intent, execution_summary, and review checklists.

Design constraints:
- No storage coupling. Purely text templates.
- Consume context via parameters only. No server-side state.
- Keep content small and skimmable; the client may prefill and edit.
"""

from typing import List
from mcp.server.fastmcp.prompts.base import UserMessage, AssistantMessage


async def prompt_execution_intent_template(
    task_title: str = "",
    task_description: str = ""
) -> List:
    return [
        UserMessage(
            f"""
Draft an execution_intent for this task:
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
    task_title: str = "",
    files_changed: str = ""
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
    task_title: str = "",
    execution_summary: str = ""
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
- [ ] Matches execution_intent
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
Plan-Manager: AI Agent Usage Guide (concise)

Core workflow per task:
1) get_current_context → select_first_story → select_first_unblocked_task
2) Draft execution_intent → request_approval_tool
3) After approval → update_task(status=IN_PROGRESS)
4) Do edits within client roots (client-enforced)
5) Draft execution_summary → update_task(status=DONE, execution_summary)
6) generate_changelog/publish_changelog_tool → append markdown client-side

Key tools:
- Context: get_current_context, select_first_story, select_first_unblocked_task, advance_to_next_task, workflow_status
- Plans: create_plan, get_plan, update_plan, delete_plan, list_plans, set_current_plan
- Stories: create_story, get_story, update_story, delete_story, list_stories
- Tasks: create_task, get_task, update_task, delete_task, list_tasks, explain_task_blockers, set_current_task
- Approvals: request_approval_tool, approve_item_tool
- Changelog: preview_changelog, generate_changelog, publish_changelog_tool (returns markdown)

Prompts: execution_intent_template, execution_summary_template, review_checklist
Roots: client-managed; server does not validate file access
Elicitation: client-led; server may offer optional prompt scaffolds
Guardrails: approval-required before leaving TODO (env-flag)
"""
        )
    ]


async def prompt_planning_suggest_work_items(
    description: str = "",
) -> List:
    """Suggest Plan/Story/Task creation based on SemVer-aligned scope."""
    return [
        UserMessage(
            f"""
Given this short description, classify scope and propose work items:

Description:
{description}

Guidance (SemVer):
- MAJOR → new Plan (backward-incompatible/fundamental changes)
- MINOR → new Story (backward-compatible feature)
- PATCH → Tasks (discrete unit of work for AI agent/bug fix/maintenance)

Return JSON only with this shape:
{{
  "classification": "MAJOR|MINOR|PATCH",
  "proposals": [
    {{ "type": "plan|story|task", "title": "...", "description": "..." }}
  ]
}}
"""
        ),
        AssistantMessage(
            """
{
  "classification": "PATCH",
  "proposals": [
    {
      "type": "task",
      "title": "Implement workflow_status guide",
      "description": "Add concise docs explaining workflow_status outputs and next actions."
    }
  ]
}
"""
        ),
    ]


def register_workflow_prompts(mcp_instance) -> None:
    """Register minimal workflow prompts on the MCP instance."""
    # Planning prompt: suggest work items per SemVer mapping
    mcp_instance.prompt(
        name="planning_suggest_work_items",
        title="Planning: Suggest Work Items",
        description="Given a short description, suggest Plan/Story/Tasks per SemVer mapping",
    )(prompt_planning_suggest_work_items)

    mcp_instance.prompt(
        name="execution_intent_template",
        title="Execution Intent Template",
        description="Template to draft execution_intent before starting a task",
    )(prompt_execution_intent_template)

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
