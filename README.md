# Plan Manager

Sync AI agent(s) and models around common goals and constraints.

## Overview

AI agents supported by models operate in a limited context window. If the work is larger, the developer needs to periodically align the agent with plans. If multiple LLMs or agents perform different tasks, for example, to optimize costs, they need to be synchronized. Plan Manager makes it easier to align agents and LLMs with a plan under user-defined constraints.

## Positioning

For large projects we use project management systems like Jira or Linear. With their help, leaders coordinate work of developers. 

Plan Manager is a tool for a developer or orchestrator to coordinate the work of one or more agents or LLM(s). For example, ask an expensive thinking LLM to create a plan and document it in Plan Manager. Delegate work items (stories, tasks) to less expensive models. Review the summary of work before and after the work item is completed, correct deviations from the plan. Export the report to the changelog and/or to larger project management systems.

## Core concepts

- Plan: container for stories.
- Story: user-facing goal; contains tasks.
- Task: discrete unit of agent work.
- Statuses: apply to plans, stories, and tasks; primary progression is TODO → IN_PROGRESS → PENDING_REVIEW → DONE; side states: BLOCKED, DEFERRED.
- Dependencies: tasks/stories may block others.
- Priority: 0–5 (0 is highest).
- Approvals: optional guardrail before progressing status.

## Usage

See project workflow in [.cursor/rules/project-management.mdc](.cursor/rules/project-management.mdc)
See [docs/agent-usage-guide.md](docs/agent-usage-guide.md)

## Development

See [contributing.md](contributing.md)
