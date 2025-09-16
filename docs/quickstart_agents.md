Plan Manager: Quickstart for Agents

- Concepts
  - Plan (epic/major), Story (what/why, minor), Task (how, patch).
  - IDs (plan/story/task) come from context; set via set_current_*.

- Happy paths
  - Planning: create_stories → create_story; create_tasks → create_task; optional for bigger tasks: /create_steps → create_task_steps.
  - Execution:
    - Start: approve_task on a TODO task (auto‑seeds a minimal step if none) → IN_PROGRESS; or create_task_steps → approve_task.
    - Review: submit_for_review(summary) → PENDING_REVIEW; approve_task → DONE (returns changelog); if changes: request_changes(feedback) → IN_PROGRESS → resubmit.

- Guardrails
  - Dependencies gate for TODO → IN_PROGRESS.
  - Changelog comes from execution_summary (submit_for_review), not steps. Ignore any placeholder fast‑track step.

- Shapes and errors
  - Tools return structured results (e.g., ApproveTaskOut) with guidance on failure.

- Tips
  - Keep summaries short and patch‑scoped. Use set_current_* to clarify context.

See resource://plan-manager/usage-guide for details.
