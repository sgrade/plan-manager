## Plan-Manager: AI Agent Usage Guide

### Purpose
Concise, workflow-aligned instructions for MCP agents using the plan-manager server. Keep the server simple: tools enforce workflow; prompts are convenience only; roots/elicitation are client-side.

### Phase 1: Planning (SemVer-aligned)
- Given a short human description, suggest work items:
  - Use prompt `planning_suggest_work_items(description)` and propose Plan/Story/Tasks (MAJOR/MINOR/PATCH).
  - Create items via tools: `create_plan` / `create_story` / `create_task`.
  - Optionally use `review_checklist` before approvals.
  - Approve via `approve_item_tool` when the human says "approved".

### Phase 2: Execution (per task)
1. Context
   - `current_context()`; if unset: `select_first_story()` → `select_first_unblocked_task()`.
2. Intent & Approval
   - If intent missing: prompt `execution_intent_template`, then `request_approval_tool`.
   - On approval (human says "approved"): `update_task(..., status='IN_PROGRESS')`.
3. Implement
   - Perform edits within client-approved roots (client-owned).
4. Summary & Done
   - Prompt `execution_summary_template`, then `update_task(..., status='DONE', execution_summary)`.
5. Changelog
   - `publish_changelog_tool(version?, date?)` → returns markdown; client appends locally.
6. Advance
   - `advance_to_next_task()` (human says "next").

### Action hints from workflow_status
- Call `workflow_status()` to get `next_actions` and `actions` (structured hints: `tool`/`prompt` + `payload_hints`).
- Prefer `actions` to reduce mapping errors; fall back to `next_actions` text.

### Helpful Tools (by area)
- Context: `current_context`, `select_first_story`, `select_first_unblocked_task`, `advance_to_next_task`, `workflow_status`
- Plans: `create_plan`, `get_plan`, `update_plan`, `delete_plan`, `list_plans`, `set_current_plan`
- Stories: `create_story`, `get_story`, `update_story`, `delete_story`, `list_stories`
- Tasks: `create_task`, `get_task`, `update_task`, `delete_task`, `list_tasks`, `explain_task_blockers`, `set_current_task`
- Approvals: `request_approval_tool`, `approve_item_tool`
- Changelog: `preview_changelog`, `generate_changelog`, `publish_changelog_tool` (returns markdown)

### Prompts (convenience only)
- Planning: `planning_suggest_work_items`, `review_checklist`
- Execution: `execution_intent_template`, `execution_summary_template`, `agent_usage_guide`
Note: Prompts produce text only.

### Short human commands (examples)
- **approved**: Call `approve_item_tool` for current item; if task was TODO with intent, proceed to IN_PROGRESS
- **next**: Call `advance_to_next_task`
- **status**: Call `workflow_status` and summarize next steps; execute first `actions` item if safe
- **intent**: Call `execution_intent_template` then `request_approval_tool`
- **summary**: Call `execution_summary_template` then `update_task` to DONE

### Guardrails
- Approval-required (env-flag): Items must be approved before leaving TODO.
- Use `workflow_status()` to understand readiness and next actions.

### Happy-path checklist per task
- [ ] Context selected (story, task)
- [ ] Intent drafted and approval requested
- [ ] Approved; status set to IN_PROGRESS
- [ ] Work done within client-scoped roots
- [ ] Summary written; status set to DONE
- [ ] Changelog markdown generated and appended client-side