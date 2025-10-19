# Plan Manager — Usage Guide

This guide is for agents using the Plan Manager MCP server. It summarizes the workflow, tools, and guardrails the server enforces.

## Overview

Plan Manager is a tool for a single developer or orchestrator to coordinate the work of one or more AI agents or models.

## Core concepts
- Plan: epic/major-level scope that groups stories.
- Story: user-facing outcome (the WHAT and WHY), minor-level; contains tasks.
- Task: implementation unit for the agent (the HOW), patch-level; contains optional steps and changelog entries.
- Context IDs: current plan/story/task are read from server-side state and can be set via `set_current_plan`, `set_current_story`, `set_current_task`.

## Commands (tools)

### Workflow Tools
- **start_task** — approve implementation plan and start work (Gate 1: TODO → IN_PROGRESS)
- **submit_for_review(changelog_entries)** — submit work for code review (IN_PROGRESS → PENDING_REVIEW)
- **approve_task** — approve code review (Gate 2: PENDING_REVIEW → DONE)
- **finalize_task(task_id, category, commit_type)** — **RECOMMENDED**: approve + generate changelog + commit (Gate 2 convenience)
- **request_changes(feedback)** — request modifications (PENDING_REVIEW → IN_PROGRESS)

### Task Management Tools
- list_*, create_*, update_*, delete_*, set_current_* — manage items and selection
- **create_task_steps(steps)** — define implementation steps (replaces existing steps)

### Artifact Generation Tools
- **generate_changelog_entry(task_id, category)** — generate keepachangelog.com entry
- **generate_commit_message(task_id, commit_type)** — generate conventional commit message

### Status and Context Tools
- **report**, **get_current** — status and context helpers

All tools return structured results. On failure, responses include human-readable guidance.

Result shape essentials (for agents):
- Each workflow tool returns `next_actions` with an explicit `who` field (e.g., USER, AGENT) and a `recommended` flag to steer behavior.
- Use `set_current_*` to manage context; operations act on the current selection when IDs are omitted.

### Result schema at a glance

```text
NextAction {
  kind: "tool" | "prompt" | "instruction",
  name: string,            // e.g., "approve_task", "submit_for_review"
  label: string,           // human-readable
  who: "USER" | "AGENT" | "AGENT_AFTER_USER_APPROVAL" | "EITHER",
  recommended: boolean,
  blocked_reason?: string,
  arguments?: object       // tool/prompt arguments when applicable
}

TaskWorkflowResult {
  success: boolean,
  message: string,
  task?: TaskOut,
  gate?: "READY_TO_START" | "EXECUTING" | "AWAITING_REVIEW" | "DONE" | "BLOCKED",
  action: string,          // enum of the operation performed
  next_actions: NextAction[],
  changelog_snippet?: string
}
```

## Prompts (assisted planning)
- `/create_plan`, `/create_stories`, `/create_tasks`, `/create_steps` propose content; tools create items. Always get explicit user approval before creation.

## Examples: Tool parameter types

- Priority (integer 0–5, 0 is highest).
  - `priority: 2` → accepted
  - `priority: 2.0` → accepted (coerced to 2)
  - `priority: 2.5` → rejected with a clear message, e.g.:
    - "Invalid type for parameter 'priority': expected integer, got non-integer number 2.5."

- Status (string)
  - `status: "IN_PROGRESS"` → accepted
  - Mixed case strings are normalized (e.g., `"in_progress"` → `IN_PROGRESS`), invalid values are rejected with allowed options listed.

- IDs
  - For tasks, either use a fully-qualified id (`<story_id>:<task_id>`) or a local id that is unique within the current story.
