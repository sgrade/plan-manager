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


def register_workflow_prompts(mcp_instance) -> None:
    """Register minimal workflow prompts on the MCP instance."""

    @mcp_instance.prompt(
        name="execution_intent_template",
        title="Execution Intent Template",
        description="Template to draft execution_intent before starting a task"
    )
    async def execution_intent_template(
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

    @mcp_instance.prompt(
        name="execution_summary_template",
        title="Execution Summary Template",
        description="Template to summarize changes after completing a task"
    )
    async def execution_summary_template(
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

    @mcp_instance.prompt(
        name="review_checklist",
        title="Review Checklist",
        description="Concise checklist to review before approval"
    )
    async def review_checklist(
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
                f"""
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
