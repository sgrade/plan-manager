# Plan-Manager: Must-Have Workflow Improvements

## Scope
Non-optional changes to make the MCP plan-manager smoother for AI agents, LLMs, and humans.

## Understanding (concise)
- Workflow: Two phases are clear — Planning (SemVer-aligned scoping) and Execution (intent → approval → implement → summary → changelog). No open gaps.
- SemVer mapping: MAJOR→Plan, MINOR→Story, PATCH→Tasks. Approvals gate progress off TODO.

## Must-Haves
1. Auto-bootstrap empty state
   - When no stories/tasks exist, create a starter story ("Getting Started") and a starter task ("Select first task") and auto-select it.
   - Rationale: Removes first-run friction and enables one-shot start.

2. Select-or-create helpers (idempotent)
   - Add helper calls that accept a name and either select an existing item or create it if missing: plan, story, task.
   - Rationale: Reduces branching logic for agents; simplifies NL-to-action mapping.

3. Current selection invariants
   - Guarantee there is always at most one current story and one current task; when the selected item is deleted or completed, auto-advance/reset.
   - Rationale: Keeps workflow state consistent and predictable.

4. Auto-advance to next unblocked task
   - On task completion, automatically select the next unblocked task within the current story. If none, prompt to move story to DONE or pick another story.
   - Rationale: Minimizes manual navigation and keeps focus.

5. Execution intent/summary prompts
   - Require `execution_intent` on start and `execution_summary` on completion; prompt the caller if missing.
   - Rationale: Improves traceability and changelog quality.

6. Blocker surfacing and guidance
   - If a task is blocked (dependencies not DONE), surface blockers with actionable "unblock" suggestions and offer to select the first unblocked prerequisite.
   - Rationale: Keeps progress flowing without manual inspection.

7. Bulk list reads and parallel-safe APIs
   - Ensure list/read endpoints are efficient and safe for parallel calls; include stable IDs and pagination.
   - Rationale: Agents routinely batch queries; avoids race conditions and partial views.

8. Changelog hooks
   - Keep preview/generate. `publish_changelog_tool` returns markdown only; the client appends to its local CHANGELOG.
   - Rationale: Works for remote HTTP deployments; avoids server-side file writes.

9. Chained actions for agents (light orchestration)
   - Add prompt `planning_suggest_work_items` for SemVer-aligned proposals (JSON output: classification + proposed items).
   - Extend `workflow_status` with structured `actions: [{id,label,tool|prompt,payload_hints}]` across all states (no story, no task, TODO, IN_PROGRESS, DONE).
   - Short commands mapping (for humans): "approved"→`approve_item_tool`, "next"→`advance_to_next_task`, "status"→`workflow_status`, "intent"→prompt+`request_approval_tool`, "summary"→prompt+`update_task` DONE.
   - Rationale: Enables mostly autonomous progression with minimal typing.

10. Minimal prompts set (server-side, text only)
    - `planning_suggest_work_items`, `execution_intent_template`, `execution_summary_template`, `review_checklist`, `agent_usage_guide`.
    - Rationale: Prompts reduce typing without coupling to storage.

11. Client-owned roots and file IO
    - Roots are requested/approved/enforced by the client; server does not validate file scope. All changelog writes happen client-side.
    - Rationale: Keeps server simple and deployment-agnostic.

## Out of Scope (Nice-to-haves)
- Human UI features (tags, due dates, notifications), visual dependency graph, role-based approvals, markdown import/export.

