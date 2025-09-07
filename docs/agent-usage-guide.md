## Plan-Manager: AI Agent Usage Guide

### Purpose
Concise, workflow-aligned instructions for MCP agents using the plan-manager server.

### Quickstart: Planning + Execution (for agents)

- Planning:
  - Use prompt `planning_suggest_work_items(description)` to classify MAJOR/MINOR/PATCH and propose Plan/Story/Tasks
  - Create items with tools (`create_plan`, `create_story`, `create_task`) and approve via `approve_item_tool`

- Execution (per task):
  - Get `workflow_status` and follow `actions` (structured hints)
  - If missing intent: prompt `execution_intent_template` → `request_approval_tool`
  - After approval: `update_task(status=IN_PROGRESS)`
  - After work: prompt `execution_summary_template` → `update_task(status=DONE, execution_summary)`
  - Changelog: `publish_changelog_tool` returns markdown for client-side append

### Guardrails

- Approval requirement can be toggled via env var in the server:

```bash
REQUIRE_APPROVAL_BEFORE_PROGRESS=true  # default true
```

### Phase 1: Planning (SemVer-aligned)
- Given a short human description, suggest work items:
  - Use prompt `planning_suggest_work_items(description)` and propose Plan/Story/Tasks (MAJOR/MINOR/PATCH).
  - Prefer idempotent helpers: `select_or_create_plan` / `select_or_create_story` / `select_or_create_task`.
  - Use `create_*` only when you must force-create a distinct item even if a same-title item exists.
  - Optionally use `review_checklist` before approvals.
  - Approve via `approve_item_tool` when the human says "approved".

### Phase 2: Execution (per task)
1. Context
   - `get_current_context()`; if unset: `select_first_story()` → `select_first_unblocked_task()`.
   - Auto-bootstrap: if no stories/tasks exist, `select_first_story()` creates a "Getting Started" story and a starter task.
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
  - Includes: dependency navigation (open blocking task/story), select first unblocked prerequisite, mark story DONE when no tasks remain.

### Helpful Tools (by area)
- Context: `get_current_context`, `select_first_story`, `select_first_unblocked_task`, `advance_to_next_task`, `workflow_status`
- Plans: `select_or_create_plan`, `create_plan`, `get_plan`, `update_plan`, `delete_plan`, `list_plans`, `set_current_plan`
- Stories: `select_or_create_story`, `create_story`, `get_story`, `update_story`, `delete_story`, `list_stories`
- Tasks: `select_or_create_task`, `create_task`, `get_task`, `update_task`, `delete_task`, `list_tasks`, `explain_task_blockers`, `set_current_task`
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
- Optional env flags:
  - `REQUIRE_EXECUTION_INTENT_BEFORE_IN_PROGRESS=true`
  - `REQUIRE_EXECUTION_SUMMARY_BEFORE_DONE=true`
- Use `workflow_status()` to understand readiness and next actions.

### Pagination
- `list_plans`, `list_stories`, `list_tasks` accept `offset` and `limit` for agent-friendly batching.

### Happy-path checklist per task
- [ ] Context selected (story, task)
- [ ] Intent drafted and approval requested
- [ ] Approved; status set to IN_PROGRESS
- [ ] Work done within client-scoped roots
- [ ] Summary written; status set to DONE
- [ ] Changelog markdown generated and appended client-side