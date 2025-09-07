# Plan Manager

Project management tool with MCP (Model Context Protocol) interface to assist AI agents. 

## Overview

AI agents backed by LLMs operate within a limited context window. If the work is larger, a developer needs to periodically reconcile the agent with the plans. If multiple LLMs or agents do different pieces of work, e.g to optimize costs, we need to sync them. Plan Manager makes it easier to reconcile agent(s) and LLM(s) with the plan(s) under user-specified constraints.

## Positioning

For large projects we use project management systems like Jira or Linear. With them, leaders coordinate work of multiple developers. 

Plan Manager is a tool for a single developer to coordinate work of one or several agents and LLM(s). For example, ask an expensive thinking LLM to sketch the plan and document it with Plan Manager. Delegate work items (stories, tasks) to less expensive LLMs. Review work summary before and after execution of a work item, correct the deviations. Export the report to changelog and/or to larger project management systems.

## Core concepts

- Plan: container for stories.
- Story: user-facing goal; contains tasks.
- Task: discrete unit of agent work.
- Statuses: apply to plans, stories, and tasks; primary progression is TODO → IN_PROGRESS → DONE; side states: BLOCKED, DEFERRED.
- Dependencies: tasks/stories may block others.
- Priority: 0–5 (0 is highest).
- Approvals: optional guardrail before progressing status.

## Usage

See project workflow in [.cursor/rules/project-management.mdc](.cursor/rules/project-management.mdc)
See [docs/agent-usage-guide.md](docs/agent-usage-guide.md)

## Development

See [contributing.md](contributing.md)
