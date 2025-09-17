# AGENTS.md

This file guides agents that use the Plan Manager MCP server.

## Usage
- Quickstart: see `docs/quickstart_agents.md` (concise)
- Full guide: see `docs/usage_guide_agents.md` (details)
- Triage policy and dashboards: see `docs/triage_guide.md`

## Setup
- Start server: `uv run pm`
- Endpoint: `http://localhost:3000/mcp`

## Workflow (very short)
- Context: `set_current_plan` → `set_current_story` → `set_current_task`
- At TODO: ask the user “What would you like to do?” → `/create_steps` → `create_task_steps` → `approve_task`, or `approve_task` to start now
- Review: `submit_for_review(summary)` → show execution_summary → user runs `approve_task` or `request_changes(feedback)`

## Notes
- Dependency gate for TODO→IN_PROGRESS; changelog from `execution_summary`.
- After server reloads, the client (Cursor) may need manual reconnect.
- Configuration reference: see `docs/config_reference.md`.
