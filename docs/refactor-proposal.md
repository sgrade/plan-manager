## Refactor proposal: workflow-aligned plan-manager

### Goals
- Convenience-first development workflow driven by the MCP tools
- Single active context with explicit defaults: current plan, story, task
- Simple, maintainable data model; keep ephemeral UI/session state out of core models
- Explicit propose/approve/complete cycle around each coding step

### Current capabilities (baseline)
- Multi-plan storage under `todo/<plan_id>/plan.yaml` with strict index at `todo/plans/index.yaml`
- Domain: `Plan(WorkItem)`, `Story(WorkItem)`, `Task(WorkItem)`; IDs derived from titles with unique suffixing
- Context defaults: current plan (global), plus per-plan `state.yaml` with `current_story_id`, `current_task_id`
- Tools: plan/story/task tools with optional payloads that default to current context; context tools to set/select and auto-advance
- Archive removed; use plan status instead

### Workflow model (new)
Use Story/Task as the unit of planned change, with per-item execution fields and an optional activity log:

- Item-level fields on Story/Task (ephemeral, updated per iteration)
  - execution_intent: short checklist before work (objective, scope, acceptance)
  - execution_summary: short summary after work (what changed, where)
  - approval: { requested_by?, approved_by?, approved_at?, notes? }
  - status continues to drive flow (TODO → IN_PROGRESS → DONE; BLOCKED/DEFERRED as needed)

- Optional activity log: `todo/<plan_id>/activity.yaml`
  - Append-only events (approval requested/granted, started, completed) with timestamps
  - Keeps history separate from core plan data

### New tools
- request_approval_for_item(item_type, item_id?, execution_intent) -> StoryOut/TaskOut
  - item_id optional; defaults to current story/task
  - saves execution_intent and marks approval.requested
  - records an activity entry (required)

- approve_item(item_type, item_id?, approved: bool, notes?) -> StoryOut/TaskOut
  - sets approved metadata (and optional notes)
  - records an activity entry (required)

- Status transitions use existing update tools
  - update_story/update_task change status to IN_PROGRESS or DONE and may set execution_summary
  - each update that changes status records an activity entry (required)

- Changelog utilities (see below)

Notes
- Tools should validate that referenced story/task exists in the current plan
- Enforce a simple happy-path state machine; reject invalid transitions

### MCP feature integration (beyond tools)
- Prompts (server feature) [MCP Spec, 2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18)
  - Provide minimal templates to prefill execution_intent and execution_summary, plus a lightweight review checklist
  - Keep prompts small and composable; they’re UI conveniences, not logic or storage

- Roots (client feature) [Cursor MCP support](https://docs.cursor.com/en/context/mcp#protocol-support)
  - Client requests/approves roots and enforces edit scoping
  - Server does not implement roots or scope validation; at most, it may suggest paths (advisory)

- Elicitation (client feature) [Cursor MCP support](https://docs.cursor.com/en/context/mcp#protocol-support)
  - For PENDING_APPROVAL proposals missing key details, the client may issue structured follow-ups
  - Server may offer an optional prompt to scaffold such follow-ups; avoid server-side branching logic

Design principles
- Tools remain the primary integration point; prompts/roots/elicitation are opt-in accelerators
- No hidden side effects; proposals, approvals, and state transitions are explicit via tools
- Maintainability: keep prompts simple; avoid coupling prompts to storage formats or server-side state

### Defaults and current-context behavior (unchanged, documented)
- get_plan(payload?) → current plan if omitted
- get_story(payload?) → current story of current plan if omitted; error if unset
- list_tasks(payload?) → current story if story_id omitted; empty if no current story
- get_task(payload?) → current task of current story if omitted; error if unset
- context tools: `select_first_story`, `select_first_unblocked_task`, `advance_to_next_task`

### Repositories and schemas (new)
- activity_repository.py
  - Append-only event log for `todo/<plan_id>/activity.yaml` (write/read/query by plan)

- schemas/inputs.py (new types)
  - RequestApprovalIn(item_type, item_id?, execution_intent)
  - ApproveItemIn(item_type, item_id?, approved, notes?)
  - Changelog inputs: GenerateChangelogIn(version?, date?), PublishChangelogIn(target_path?)

- schemas/outputs.py (new types, optional)
  - ActivityEventOut (for debugging/inspection), ChangelogPreviewOut

- tools
  - approval tools: request_approval_for_item, approve_item
  - changelog tools: preview_changelog, generate_changelog, publish_changelog

### Guardrails (soft enforcement)
- The Cursor agent follows planning rules; plan-manager records the state
- The server MUST enforce a precondition (env-flag controlled) that items must be APPROVED before status transitions off TODO (e.g., to IN_PROGRESS/DONE)

### Implementation outline
1) Add `activity_repository.py` (append-only per-plan event log)
2) Add approval and changelog schemas/tools; register in `server.py`
3) Document defaults for get/list tools and current-context tools
4) Changelog integration
   - Tools:
     - preview_changelog() → render pending activity log entries as markdown sections grouped by date/version
     - generate_changelog(version?, date?) → produce consolidated markdown snippet from recent activity
     - publish_changelog(target_path='CHANGELOG.md') → append or open PR-ready diff; idempotent by entry id
   - Activity → Changelog mapping:
     - Story/Task DONE with execution_summary → “Added/Changed/Fixed” bucket based on status/labels (simple heuristic)
     - Include scope ids and links to files touched (if provided in result_hint)

### Migration
- Backward compatibility intentionally ignored; adopt new tools and storage layout

### Rationale
- Keeps domain clean; “current” and “workflow” live in simple per-plan sidecar files
- Provides explicit propose/approve/complete steps that match the development workflow
- Maintains simplicity: serial execution with context helpers
