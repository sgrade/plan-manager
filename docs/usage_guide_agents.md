# Plan Manager — Usage Guide

This guide is for agents using the Plan Manager MCP server. It summarizes the workflow, tools, and guardrails the server enforces. Keep it handy; the short Quickstart in InitializeResult shows the essentials, and this document provides the authoritative details.

## Overview

Plan Manager is a tool for a single developer or orchestrator to coordinate the work of one or more AI agents or models.

## Core concepts
- Plan: epic/major-level scope that groups stories.
- Story: user-facing outcome (the WHAT and WHY), minor-level; contains tasks.
- Task: implementation unit for the agent (the HOW), patch-level; contains optional steps and an execution summary.
- Context IDs: current plan/story/task are read from server-side state and can be set via `set_current_plan`, `set_current_story`, `set_current_task`.

## Commands (tools)
- list_*, create_*, update_*, delete_*, set_current_* — for plans, stories, tasks
- approve_task — approve current task (state-based, deterministic)
- submit_for_review(summary) — move IN_PROGRESS → PENDING_REVIEW
- request_changes(feedback) — move PENDING_REVIEW → IN_PROGRESS
- create_task_steps(steps) — replace task steps (full replacement)
- report, get_current — status and context helpers

All tools return structured results. On failure, responses include human-readable guidance.

## Deterministic rules & guardrails
- Selection (client‑driven):
  - Always list tasks and then explicitly select one: `list_tasks` → `set_current_task <id>`.
  - The server never auto‑selects a task; approvals operate on the current task only.
  - If no current task is set, approval tools return a clear error.
- Gate 1: Pre‑Execution approval (start work):
  - Plan‑first path: draft steps via the `/create_steps` prompt, wait for user approval, then `create_task_steps`, then `approve_task`.
  - Fast‑track path: call `approve_task` directly; the server will seed a minimal placeholder step.
  - Steps JSON is validated server‑side; invalid or empty arrays are rejected with actionable messages.
- Dependency gate:
  - TODO → IN_PROGRESS only if unblocked; blocked approvals fail with a clear "BLOCKED" message.
- Changelog:
  - Generated from `execution_summary` on PENDING_REVIEW → DONE via `approve_task`.
  - Steps are not required for a changelog; ignore the placeholder fast‑track step in summaries.
- State transitions (enforced):
  - TODO → IN_PROGRESS (via `approve_task`, dependency gate; steps optional)
  - IN_PROGRESS → PENDING_REVIEW (via `submit_for_review(summary)`)
  - PENDING_REVIEW → DONE (via `approve_task`)
  - PENDING_REVIEW → IN_PROGRESS (via `request_changes(feedback)`)
- Error handling:
  - The server returns prescriptive, human‑readable guidance on failure. Do not infer or guess—follow the message.

## Prompts (assisted planning)
- `/create_plan`, `/create_stories`, `/create_tasks`, `/create_steps` propose content; tools create items. Always get explicit user approval before creation.

## Tips for agents
- Keep `execution_summary` short, user-visible, and patch-scoped (what changed, where).
- When the user gives feedback in chat, call `request_changes(feedback)` to reopen the task for rework.
- Use `set_current_*` to clarify context before approval or review actions.
- If you call `approve_task` on a `TODO` task and the operation fails due to a dependency, use the `report` tool to inspect the blockers and inform the user.

## Examples: Tool parameter types

- Priority (integer 0–5)
  - `priority: 2` → accepted
  - `priority: 2.0` → accepted (coerced to 2)
  - `priority: 2.5` → rejected with a clear message, e.g.:
    - "Invalid type for parameter 'priority': expected integer, got non-integer number 2.5."

- Status (string)
  - `status: "IN_PROGRESS"` → accepted
  - Mixed case strings are normalized (e.g., `"in_progress"` → `IN_PROGRESS`), invalid values are rejected with allowed options listed.

- IDs
  - For tasks, either use a fully-qualified id (`<story_id>:<task_id>`) or a local id that is unique within the current story.
