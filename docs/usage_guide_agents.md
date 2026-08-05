# Plan Manager — Usage Guide

This guide is for agents using the Plan Manager MCP server. It summarizes the workflow, tools, and guardrails the server enforces.

## Overview

Plan Manager coordinates one or more AI agents around explicit plan scope.

## Core concepts
- Plan: epic/major-level scope that groups stories.
- Story: user-facing outcome (the WHAT and WHY), minor-level; contains tasks.
- Task: implementation unit for the agent (the HOW), patch-level; contains optional steps and changelog entries.
- Explicit scope: every plan-scoped tool requires `plan_id`; workflow mutations also require `task_id`.
- Per-plan current story/task: `set_current_story` and `set_current_task` are discovery helpers only; mutations must still pass explicit ids.

## Commands (tools)

### Workflow Tools
- **start_task(plan_id, task_id)** — approve implementation plan and start work (Gate 1: TODO → IN_PROGRESS)
- **submit_pr(plan_id, task_id, changes)** — submit work for code review (IN_PROGRESS → PENDING_REVIEW)
- **approve_pr(plan_id, task_id)** — approve code review (Gate 2: PENDING_REVIEW → DONE)
- **merge_pr(plan_id, task_id, changelog_category, commit_type)** — **RECOMMENDED**: approve + generate changelog + commit (Gate 2 convenience)
- **request_pr_changes(plan_id, task_id, feedback)** — request modifications (PENDING_REVIEW → IN_PROGRESS)

### Task Management Tools
- `list_*`, `create_*`, `get_*`, `update_*`, `delete_*`, `set_current_*` — all plan-scoped calls require `plan_id`
- **create_task_steps(plan_id, task_id, steps)** — define implementation steps (replaces existing steps)

### Artifact Generation Tools
- **generate_changelog_entry(plan_id, task_id, category)** — generate keepachangelog.com entry
- **generate_commit_message(plan_id, task_id, commit_type)** — generate conventional commit message

### Status and Context Tools
- **report(plan_id, scope)** and **get_current(plan_id)** — status and context helpers

All tools return structured results on success. Mutation failures now raise errors (MCP `isError=true`) and include a `structured_recovery=` JSON payload in the error text.

Result shape essentials (for agents):
- `start_task`, `submit_pr`, `approve_pr`, and `request_pr_changes` return `TaskWorkflowResult` with `next_actions`.
- `merge_pr` returns `TaskFinalizationOut` (no `next_actions` field).
- `next_actions.arguments` includes `plan_id` and full `task_id` values so scope can be forwarded mechanically.
- `next_actions.pending_arguments` lists required tool arguments the server cannot infer; the agent must supply them from real context before execution.
- Gate-crossing mutation actions are marked `AGENT_AFTER_USER_APPROVAL` until the user approves at that gate.
- Scope mismatch errors name both the supplied `plan_id` and the mismatched id.

## Compatibility map (v2 explicit scope)

- Removed: `set_current_plan`
- Changed: `get_current(plan_id)` (was parameterless global current)
- Changed: every plan-scoped tool now requires `plan_id`
- Changed: workflow mutations require explicit `task_id`
- Unchanged global tools: `create_plan`, `list_plans`, `get_plan(plan_id)`

### Result schema at a glance

```text
NextAction {
  kind: "tool" | "prompt" | "instruction",
  name: string,            // e.g., "approve_pr", "submit_pr"
  label: string,           // human-readable
  who: "USER" | "AGENT" | "AGENT_AFTER_USER_APPROVAL" | "EITHER",
  recommended: boolean,
  blocked_reason?: string,
  arguments?: object,      // tool/prompt arguments the server can provide
  pending_arguments?: string[] // required argument names the agent must provide
}

TaskWorkflowResult {
  success: boolean,
  message: string,
  plan_id?: string,
  task?: TaskOut,
  gate?: "READY_TO_START" | "EXECUTING" | "AWAITING_REVIEW" | "DONE" | "BLOCKED",
  action: string,          // enum of the operation performed
  next_actions: NextAction[],
  changelog_snippet?: string
}
```

## Prompts (assisted planning)
- `/create_plan`, `/create_stories`, `/create_tasks`, `/create_steps` propose content; tools create items.
- Prompts now carry explicit ids in instructions (`plan_id`, `story_id`, `task_id`) for follow-up tool calls.
- Always get explicit user approval before creation.

## Examples: Tool parameter types

- Priority (integer 0–5, 0 is highest / most urgent).
  - `priority: 2` → accepted
  - `priority: 2.0` → accepted (coerced to 2)
  - `priority: 2.5` → rejected with a clear message, e.g.:
    - "Invalid type for parameter 'priority': expected integer, got non-integer number 2.5."

- Status (string)
  - `status: "IN_PROGRESS"` → accepted
  - Mixed case strings are normalized (e.g., `"in_progress"` → `IN_PROGRESS`), invalid values are rejected with allowed options listed.

- IDs
  - For tasks, use fully-qualified ids (`<story_id>:<task_id>`) when possible.
  - Every plan-scoped call includes `plan_id`, e.g. `concurrency_stability`.
