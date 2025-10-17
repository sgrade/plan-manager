"""Minimal workflow prompts for convenience only.

These prompts provide small, composable templates to assist the user in
authoring execution_intent, execution_summary, and review checklists.

Design constraints:
- No storage coupling. Purely text templates.
- Consume context via parameters only. No server-side state.
- Keep content small and skimmable; the client may prefill and edit.
"""

from mcp.server.fastmcp.prompts.base import AssistantMessage, Message, UserMessage


# TODO: Rewrite this prompt for a story review checklist. Then register it.
async def prompt_review_checklist(
    task_title: str = "", execution_summary: str = ""
) -> list[Message]:
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
