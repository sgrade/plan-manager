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

## Happy paths
### Planning (assisted optional)
- `/create_stories` → call `create_story` for each approved proposal.
- `/create_tasks` → call `create_task` for each approved proposal.
- Optional for larger tasks: `/create_steps` → `create_task_steps` before starting work.

### Execution (two-gate, PR-style)
1) Start work (TODO → IN_PROGRESS)
   - Default fast‑track: run `approve_task` on a TODO task. If no steps exist, the server auto‑seeds a minimal step and advances.
   - If steps were created via `/create_steps`: call `create_task_steps`, then `approve_task`.

2) Review
   - `submit_for_review(summary)` → PENDING_REVIEW (summary is required and drives the changelog).
   - Approve: `approve_task` → DONE, server returns a changelog snippet.
   - Changes: `request_changes(feedback)` → IN_PROGRESS; revise (optionally update steps), then submit again.

## Deterministic rules & guardrails
- Dependency gate: TODO → IN_PROGRESS only if the task is unblocked.
- Steps:
  - Not required for fast‑track; the server seeds a minimal placeholder.
  - Use `create_task_steps` when you want explicit pre‑execution review.
- Changelog:
  - Generated from the `execution_summary` provided to `submit_for_review` when moving PENDING_REVIEW → DONE.
  - Steps are not required for a changelog; ignore the placeholder fast‑track step in summaries.
- State transitions (enforced):
  - TODO → IN_PROGRESS (via `approve_task`, dependency gate; steps optional)
  - IN_PROGRESS → PENDING_REVIEW (via `submit_for_review(summary)`)
  - PENDING_REVIEW → DONE (via `approve_task`)
  - PENDING_REVIEW → IN_PROGRESS (via `request_changes(feedback)`)

## Prompts (assisted planning)
- `/create_plan`, `/create_stories`, `/create_tasks`, `/create_steps` propose content; tools create items. Always get explicit user approval before creation.

## Tips for agents
- Keep `execution_summary` short, user-visible, and patch-scoped (what changed, where).
- When the user gives feedback in chat, call `request_changes(feedback)` to reopen the task for rework.
- Use `set_current_*` to clarify context before approval or review actions.
