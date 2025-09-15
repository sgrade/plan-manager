# Plan Manager

Sync AI agent(s) and models around common goals and constraints.

## Overview

AI agents supported by models operate in a limited context window. If the amount of work is greater, there is a need to periodically coordinate the agent with broader plans. Moreover, if several AI models or agents perform different tasks, for example, to optimize costs, they need to be synchronized. The Plan Manager makes it easier to coordinate agents and LLMs with a plan according to user-defined constraints.

## Positioning

For large projects we use project management systems like Jira or Linear. With their help, leaders coordinate work of developers. 

Plan Manager is a tool for a single developer or orchestrator to coordinate the work of one or more AI agents or models. For example, ask an expensive thinking model to create a plan and document it in Plan Manager. Delegate work items (stories, tasks) to less expensive models. Review the summary of work before and after the work item is completed, correct deviations from the plan. Export the report to the changelog and/or to larger project management systems.

## Core concepts

- Plan: container for stories.
- Story: user-facing goal; contains tasks.
- Task: discrete unit of agent work.
- Statuses: apply to plans, stories, and tasks; primary progression is TODO → IN_PROGRESS → PENDING_REVIEW → DONE; side states: BLOCKED, DEFERRED.
- Approvals: optional guardrail before progressing status.
- Dependencies: tasks/stories may block others.
- Priority: 0–5 (0 is highest).

## Usage

### Docs

The overview diagrams are in [docs/project_workflow.md](docs/project_workflow.md)

The project workflow description is in [.cursor/rules/project-management.mdc](.cursor/rules/project-management.mdc)

### Hints

Use `/` in the client (Cursor) chat window to list Plan Manager prompts (instructions, templates to interact with the server).

Use MCP inspector to learn more about Plan Manager capabilities - [doc](dev/mcp-inspector/README.md).

## Development

See [contributing.md](contributing.md)
