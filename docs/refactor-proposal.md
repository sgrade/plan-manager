# Refactoring & Improvement Proposals

## Task Execution Workflow – Align with Simplified Agile Flow

Goal: keep the “happy path” simple and deterministic, while supporting a clean rework loop during post‑execution review.

### Current Highlights
- Steps serve as the “ready” gate before starting work (TODO → IN_PROGRESS).
- approve_task on PENDING_REVIEW moves a task to DONE and returns a changelog snippet.
- We now implicitly fast‑track TODO tasks when approve_task is called and steps are missing (seeds a minimal step).

### Proposed Changes (Task-level)
- Approve semantics (tool‑driven, no prompt):
  - TODO:
    - If blocked by dependencies → return structured error listing blockers.
    - Else if steps exist → IN_PROGRESS.
    - Else → seed steps=[{"title":"Fast-tracked by user."}] and IN_PROGRESS.
  - PENDING_REVIEW → DONE (emit changelog snippet).
  - Other states → structured guidance (what’s missing / next action).

- Post‑execution review (rework path):
  - New tool: `request_changes(story_id, task_id, feedback: str)`
    - Transition: PENDING_REVIEW → IN_PROGRESS
    - Persist feedback to the task (append‑only)
    - Increment `rework_count`
  - Submit for review remains: IN_PROGRESS → PENDING_REVIEW via `submit_for_review`.

### State Machine Updates
- Allow PENDING_REVIEW → IN_PROGRESS only via `request_changes` (with non‑empty feedback).
- Keep existing gate for TODO → IN_PROGRESS: unblocked + steps present or implicit fast‑track seed.

### Data Model Additions
- Task.review_feedback: list of items `{ message: str, at: iso8601, by?: str }` (append‑only)
- Task.rework_count: int (default 0)
- Optional: Task.steps_history: list of snapshots for audit (full replacements of steps)

### Tools & Contracts
- approve_task: returns structured result (ApproveTaskOut) for both success and failure.
- request_changes: returns OperationResult(success, message).
- submit_for_review: unchanged; requires IN_PROGRESS; sets execution_summary and moves to PENDING_REVIEW.

### Prompts
- Keep prompts for generative work only (create_plan/create_stories/create_tasks/create_steps).

### Activity & Telemetry (optional)
- Emit events: review_requested, changes_requested(feedback), resubmitted_for_review, review_approved.
- Changelog: include “(reworked x times)” when `rework_count > 0`.

### Docs & Diagrams
- Task Execution diagram:
  - Assisted path: `/create_steps` → `create_task_steps` → `approve_task` → IN_PROGRESS
  - Fast‑track path: `approve_task` seeds minimal step → IN_PROGRESS
  - Post‑execution: `submit_for_review` → PENDING_REVIEW →
    - approve_task → DONE (+changelog), or
    - request_changes(feedback) → IN_PROGRESS (rework loop)

### Backward Compatibility
- Not required. Existing behavior already matches implicit fast‑track; we add the rework loop explicitly.

### Rollout Steps
1) Add `request_changes` tool and data model fields.
2) Update `update_task` to restrict PENDING_REVIEW → IN_PROGRESS to `request_changes` only.
3) Add optional `create_rework_plan` prompt (if desired).
4) Update documentation and Mermaid diagrams (already in progress).