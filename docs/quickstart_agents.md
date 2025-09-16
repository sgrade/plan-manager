Plan Manager: Quickstart for Agents

- Context: set via `set_current_plan`, `set_current_story`, `set_current_task`.

- Plan/Breakdown:
  - `/create_stories` → `create_story`
  - `/create_tasks` → `create_task`
  - Optional: `/create_steps` → `create_task_steps`

- Execute:
  - At TODO: ask “What does the user do?” → either `/create_steps` → `create_task_steps` → `approve_task`, or `approve_task` to start now (fast‑track seeds a minimal step if none).
  - Review: `submit_for_review(summary)` → show execution_summary → user runs `approve_task` (accept) or `request_changes(feedback)` (reopen; revise, then resubmit).

- Guardrails: dependency gate (TODO→IN_PROGRESS); changelog from `execution_summary`.

- Tips: keep summaries short; wait for user after context changes.

Details: see `resource://plan-manager/usage_guide_agents.md`.
