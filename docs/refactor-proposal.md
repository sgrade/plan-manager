## Refactor proposal: planning/execution workflow with MCP integration

### Goals
- Convenience-first workflow for AI agents and humans; minimal typing for standard steps
- Two clear phases: Planning (design/scope) and Execution (do/review/complete)
- Keep server simple and maintainable; prompts are convenience-only; client owns roots and file IO
- Enforce explicit propose → approve → execute → summarize cycle via tools and soft guardrails

### Phase 1: Planning (SemVer-aligned)
- Use Semantic Versioning guidance to decide the work item level (see `https://semver.org/`).
  - MAJOR: Backward-incompatible or fundamental changes → create a new `Plan`
  - MINOR: Backward-compatible feature additions → create a new `Story`
  - PATCH: Bug fixes, maintenance, or small discrete units for an agent → create `Task`s

Flow:
1) Human provides a short description of the desired change
2) Agent proposes work item(s): Plan/Story/Tasks based on SemVer mapping
3) Human reviews and edits titles/descriptions/scope
4) Human approves work items → transition to Execution

Tooling in Planning:
- Plans: `create_plan`, `get_plan`, `update_plan`, `list_plans`, `set_current_plan`
- Stories: `create_story`, `update_story`, `list_stories`
- Tasks: `create_task`, `list_tasks`
- Approvals: `request_approval_tool`, `approve_item_tool`

Prompts in Planning (server-side templates, optional):
- `execution_intent_template` to help draft intent for approval
- `review_checklist` to assist in pre-approval review

Notes:
- Prompts only produce text; they do not modify state
- Client (IDE) owns roots and file access; server does not grant/validate roots

### Phase 2: Execution
Principles:
- Default to current plan → current story → current task context
- Require approval before moving a TODO task to IN_PROGRESS (env-flag guardrail)
- Agent should advance mostly autonomously with short human commands (e.g., "approved", "next")

Flow (per Task):
1) If not selected, `select_first_story` → `select_first_unblocked_task`
2) Draft or retrieve `execution_intent` (prompt optional), then `request_approval_tool`
3) After approval, `update_task(status=IN_PROGRESS)` and perform edits (within client-managed roots)
4) Draft `execution_summary` (prompt optional), then `update_task(status=DONE, execution_summary)`
5) Changelog: `generate_changelog` or `publish_changelog_tool` → returns markdown for client-side append

Helpful Execution Tools:
- Context: `current_context`, `select_first_story`, `select_first_unblocked_task`, `advance_to_next_task`, `workflow_status`
- Tasks: `get_task`, `update_task`, `explain_task_blockers`, `set_current_task`
- Approvals: `request_approval_tool`, `approve_item_tool`
- Changelog: `preview_changelog`, `generate_changelog`, `publish_changelog_tool` (returns markdown)

Prompts in Execution (optional):
- `execution_intent_template`, `execution_summary_template`, `agent_usage_guide`

Short-command expectations (for humans):
- "approved" → Agent calls `approve_item_tool` for current task/story
- "next" → Agent calls `advance_to_next_task`
- "status" → Agent calls `workflow_status` and summarizes next actions
- "intent" → Agent calls prompt `execution_intent_template` and proposes text
- "summary" → Agent calls prompt `execution_summary_template` and proposes text

### MCP feature adoption (beyond tools)
- Prompts (server): minimal templates to reduce typing; no storage/logic coupling
- Roots (client): client requests/approves roots; server does not validate file scope
- Elicitation (client): client may ask follow-ups; server may offer optional prompts

### Guardrails
- Env-flag to require approval before leaving TODO
- `workflow_status` provides next actions and compliance hints

### Orchestration and chaining
Objective: Each prompt/tool should naturally lead to the next step with minimal human input (e.g., "approved", "next"). Keep orchestration light and client-driven.

Recommended approach (client-driven):
- Use `workflow_status` as the single source of truth to decide the next step. It already returns `next_actions` text; we will extend it to include structured action hints (tool name + payload fields) to reduce LLM mapping.
- Prompts return text the client immediately feeds into the next tool (e.g., intent → request_approval; summary → update_task DONE).
- Short human commands map to concrete actions (see below), the agent executes without re-asking.

Chained flow: Planning
1) Human provides short description
2) Prompt: planning_suggest_work_items (new) → proposes Plan/Story/Task classification (SemVer-aligned) with suggested titles/descriptions
3) Agent creates items via tools: `create_plan`/`create_story`/`create_task`
4) Prompt: review_checklist (optional) → human edits, then "approved"
5) Agent calls `approve_item_tool` for the selected items → move to Execution

Chained flow: Execution (per task)
1) `workflow_status` → if missing intent, Prompt: execution_intent_template → agent calls `request_approval_tool`
2) When approved, agent calls `update_task(status=IN_PROGRESS)` and proceeds with edits inside client-managed roots
3) After work, Prompt: execution_summary_template → agent calls `update_task(status=DONE, execution_summary)`
4) Agent calls `publish_changelog_tool` (returns markdown) → client appends locally
5) Agent calls `advance_to_next_task` (on "next")

Short commands → actions
- "approved" → `approve_item_tool` for current item
- "next" → `advance_to_next_task`
- "status" → `workflow_status` and summarize next steps
- "intent" → prompt execution_intent_template, then `request_approval_tool`
- "summary" → prompt execution_summary_template, then `update_task` DONE

Server changes kept minimal:
- Add one prompt: `planning_suggest_work_items` (returns structured JSON suggestion). Alternatively, keep as text with a fenced JSON block the agent parses.
- Extend `WorkflowStatusOut` (non-breaking) with optional `actions: [{ id, label, tool, payload_hints }]` to cut ambiguity.
- No server-side orchestrator; the client agent sequences calls based on hints and short commands.

### Refactoring plan (chained workflows)
1) Documentation (this file)
   - Document planning/execution flows with explicit chain points (done)
   - Keep `docs/agent-usage-guide.md` aligned with short-command mapping (done)
2) Prompts
   - Add `planning_suggest_work_items` (new) for SemVer-aligned item proposals
   - Keep minimal prompts: `execution_intent_template`, `execution_summary_template`, `review_checklist`, `agent_usage_guide` (done)
3) Workflow status action hints
   - Extend `WorkflowStatusOut` to include optional `actions` with `tool` and `payload_hints`
   - Keep existing `next_actions` text for backward compatibility
4) Changelog tooling
   - Confirm `publish_changelog_tool` returns markdown only (done)
5) Short-command behavior
   - In agent guide, codify mapping from short commands to tool/prompt chains (done)
6) Out of scope
   - No server-side roots or orchestration executor; client owns both

### Rationale
- Aligns planning artifacts with change magnitude (SemVer)
- Minimizes human typing and server complexity
- Keeps the happy-path explicit and auditable via tools and approvals
