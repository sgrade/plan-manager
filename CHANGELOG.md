# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed:
- Show execution summary in TaskOut and report: Expose review summaries in UI surfaces: 1) Add execution_summary to TaskOut and include it in get_task; 2) Display Review Summary in report when current task is PENDING_REVIEW to streamline code review without extra commands.
- Audit MCP tool parameter schemas: Audited MCP tools and services. Findings: 1) Priority type mismatch at transport vs domain; implemented boundary coercion with clear error messages and updated tool signatures to accept numeric types. 2) Task status string vs enum mismatch; updated tool to coerce to Status enum. 3) Minor prompt typo fixed ("Create aplan" -> "Create a plan"). Error handling improved in task tools: now raise exceptions instead of returning invalid TaskOuts.
- Establish triage labels and P0/P1/P2 criteria: Added performance labeling guidance (use area:performance with type:enhancement unless functional defect) and concrete P1 vs P2 examples. Docs updated in triage_guide.md.
- Create triage dashboard and backlog views: Defined dashboard views (P0/P1, needs‑info, by area) and documented how to access them in triage_guide.md. Removed README section to avoid duplication.
- Run initial triage pass: Applied P0/P1/P2 severities per guide, added area: labels where applicable, and marked unclear items as needs‑info. Verified triage_guide.md covers monitoring P0/P1, needs‑info, and area views.
- Set up weekly triage routine: Added weekly triage cadence and ownership details to triage_guide.md (schedule, participants, reminders, outcomes, ≤15‑min agenda).
- Quickstart polish and cross-links: Polished Quickstart wording and added a concise cross‑link to triage_guide.md; kept detailed behavior in usage_guide_agents.md.
- Configuration reference updates: Added docs/config_reference.md with env vars, defaults, and examples (reload, logging, paths, reconnect notes). Linked from contributing and AGENTS.md.

## [v0.6.0] - 2025-09-16

### Added
- Assisted planning prompts registered and made context-aware (optional args, use current plan/story/task when omitted).
- FastMCP prompt catalog with dynamic registration via `register_prompts` and `PROMPT_SPECS`.
- New prompts:
  - `create_plan` (plan with title and description)
  - `create_stories` (stories with title, description, acceptance_criteria)
  - `create_tasks` (tasks with title, description)
  - `create_steps` (PATCH-level steps suitable for changelog bullets)
- Review checklists and usage guide aligned with the documented workflow.
- Acceptance criteria in Story
- Formal way to request changes in task execution workflow

### Changed
- BREAKING: Flattened MCP tool inputs to simple parameters (no nested payload objects):
  - set_current_plan(plan_id?), set_current_story(story_id?), set_current_task(task_id?)
  - create_plan(title, description?, priority?), create_story(title, priority?, depends_on?, description?), create_task(story_id, title, priority?, depends_on?, description?)
  - get_plan(plan_id?), get_story(story_id?), get_task(story_id?, task_id?)
  - update_plan(plan_id, title?, description?, priority?, status?), update_story(story_id, title?, description?, depends_on?, priority?, status?), update_task(story_id, task_id, title?, description?, depends_on?, priority?, status?)
  - delete_plan(plan_id), delete_story(story_id), delete_task(story_id, task_id)
  - list_plans, list_stories, list_tasks
  - task_tools
- Replace usage prompts with MCP server instructions (quickstart) and resource (usage guide)

### Removed
- Remove inputs schema

### Fixed
- Prompt examples now use valid JSON (no trailing commas; corrected keys: `description` instead of `user_story`).

## [0.5.5] - 2025-09-10

### Added
- **Scoped Reporting:** The `report` command now accepts an optional scope. `report plan` provides a high-level summary of all stories, while the default `report` continues to show a detailed view of the current story.
- **Proactive Blocker Detection:** The system now automatically updates task statuses to `BLOCKED` or `TODO` based on the completion of their dependencies. This logic is triggered whenever a task is marked as `DONE`.

### Changed
- **Interactive `set_current` Commands:** The `set_current_plan`, `set_current_story`, and `set_current_task` commands now list available items if called without an ID, guiding the user to make a valid selection.
- **Improved Error Handling:** Added robust `try...except` blocks to the tool layer (`approval_tools.py`, `task_tools.py`) to catch service-level exceptions and return user-friendly, structured error messages.

## [0.5.4] - 2025-09-10

### Fixed
- Corrected a bug in the `approve_fast_track` service where it failed to find stories due to incorrect ID handling.
- Ensured that `approve_fast_track` uses fully-qualified task IDs when calling underlying services to prevent lookup failures.

### Changed
- The `approve_task` tool now requires a fully-qualified ID (`story_id:task_id`) for fast-tracking to prevent ambiguity when multiple tasks share similar local IDs.

## [0.5.3] - 2025-09-10

### Changed
- Rename `approve` tool to `approve_task`
- Structured input and output for the task approval tool
- Streamline `changelog` functionality and hook it to the `approve_task` tool
- Integrate the blocker-checking logic directly into the report service.
- Ensure that when a user runs report on a BLOCKED task, they will now see a clear, human-readable list of what needs to be done to unblock it.

### Removed
- Remove the explain_task_blockers command, simplifying the user-facing API.

## [0.5.2] - 2025-09-10

### Added
- **`prepare` command:** New command to instruct the agent to generate the implementation `steps` for a task.
- **`get_current` command:** New command to display the current context (Plan, Story, Task IDs).
- **Unified Workflow Documentation:** Added a new unified workflow diagram and explanation to `docs/project_workflow.md` for improved clarity.

### Changed
- **`status` command renamed to `report`:** To better reflect its function as a rich progress summary and avoid ambiguity with the `Status` property.
- **Task `implementation_plan` field renamed to `steps`:** For clarity and to avoid confusion with the `Plan` work item.
- **Updated `approve` command behavior:** The `approve` command is now more explicit for handling steps review and fast-tracking.
- The `delete_plan` command now properly removes the plan's directory and all associated files.

### Removed
- **`backlog` command:** Removed in favor of more explicit `list_stories`, `create_story`, and `list_tasks` commands.
- **`select_or_create_plan` command:** Removed in favor of the explicit `list_plans`, `create_plan`, and `set_current_plan` workflow.
- **`workflow_status` command:** Removed as its functionality is now better covered by the `report` and `get_current` commands.

## [0.5.1] - 2025-09-08

### Added
- MCP prompts for execution intent and summary, review checklist.
- Break development workflow into planning and execution; related convenience features.
- Implement planning/execution workflow, agent actions (workflow_status.actions), select_or_create, guardrails, pagination, client-side changelog
- Align it with the rewrtitten task-centric workflow defined in `.cursor/rules/project-management.mdc`

### Changed
- Refactor changelog tools to work with remote client.

## [0.5.0] - 2025-09-04

### Added
- Workflow-aligned plan-manager: execution intent, summary, approvals.
- Enforce WorkItem ID generation.
- Basic state management for tracking current plan, story and task.

## [0.4.0] - 2025-09-02

### Added
- Testing with mcp-inspector

### Changed
- Tweak Dockerfile and devcontainer.json to automate dev environment setup for Python.
- Add testing with mcp-inspector.
- Unify Story/Task CRUD, reduce duplication, and tighten types.
- Structure input and output.
- Refactor list_tasks service and tool for stricter structured output.
- Refactor list_stories service and tool for structured input and output.
- Unify plan management is unified with story and task management.
- Deprecate plan archive - use unified plan management instead.

## [0.3.1] - 2025-08-29

### Changed
- Replace implicit imports from plan_manager.domain (__init__.py) with explicit imports from plan_manager.domain.models to avoid accidental re-exports, reduce surface area, and lower risk of circular imports.
- Uvicorn config: TIMEOUT_GRACEFUL_SHUTDOWN from 2 to 30 and TIMEOUT_KEEP_ALIVE from 2 to 5 to avoid "ERROR - uvicorn.error:414 - Exception in ASGI application".

### Fixed
- Import logging config.
- One empty line in the end of files instead of three.

## [0.3.0] - 2025-08-28

### Added
- `plan_manager.domain.validation` module for domain-layer dependency validation.

### Changed
- Separate domain models from orchestration (services vs. data models).
- Centralize dependency validation and status transitions.
- Encapsulate file mirroring concerns.
- Enable safer plan writes and easier testing.
- Archive tools now use the repository API exclusively: `archive.delete_archived_story` performs loads/saves via `services.plan_repository`.
- Story deletion now also removes the entire story directory (`todo/<story_id>/`) best-effort, with guardrails to prevent unsafe deletes.
- Refine domain models: `Plan` validator defers dependency validation import to avoid cycles and keep domain layer pure.
- Improve typing, docstrings, and logging consistency.

### Removed
- egacy implementations related to the changed functionality.
- Outdated CLI tools.

## [0.2.3] - 2025-08-26

### Changed
- Replace SSE transport by Streamable HTTP.
- Refactor application configuration to follow Twelve-Factor App principles. All settings are now sourced from environment variables with sensible defaults. Command-line arguments have been removed for simplicity.
- Consolidate configuration logic has been into the `plan_manager.config` module.
- Unify the logging system: modules now use a consistent, centrally configured logger that inherits its settings from the main entrypoint.
- Logging now defaults to writing to `stdout` as an event stream, adhering to Twelve-Factor principles. File-based logging is now an opt-in feature for development.

### Added
- The `PLAN_MANAGER_ENABLE_FILE_LOG` variable is now set in `.devcontainer/devcontainer.json` to automatically enable file logging for a better development experience.
- Add `logs/` directory to `.gitignore` to prevent log files from being committed.

### Fixed
- Suppress ASGI app factory warning from Uvicorn by adding `factory=True` to the `uvicorn.run()` call.

## [0.2.2] - 2025-08-23

### Changed
- Split modules into `story_model.py`, `stories.py`, `plan.py`, `archive.py` for clarity.
- Explicit MCP tool registration (stories, plan, archive) from `mcp_server.py`.
- Clean imports, removed sys.path hacks, and fixed circular imports.

### Fixed
- Lint issues and missing imports; server starts cleanly with autoreload.

## [0.2.1] - 2025-08-23

### Added
- `create_task` supports `details_content` to initialize the task markdown (remote-friendly).
- New unified `update_task` handler for partial updates (title, notes, depends_on, priority, status).

### Changed
- CRUD naming alignment: `get_task`, `create_task`, `update_task`, `delete_task`. Removed legacy `show_task_handler`.
- Empty `status`/`priority` in `update_task` are treated as “no change” to ease client calls.

### Removed
- Specialize `update_task_status_handler` and `update_task_priority_handler` in favor of `update_task`.

## [0.2.0] - 2025-08-22

### Added
- Development autoreload via `uvicorn --reload` in dev workflow.
- CLI flags for reload directories, include/exclude patterns, and timeouts.
- Env flag `PLAN_MANAGER_ENABLE_FILE_LOG` to disable file logging in dev.

### Changed
- Documentation updated for SSE-only configuration and Cursor SSE setup.

### Fixed
- Faster, more predictable shutdown on reload even with long-lived SSE connections open.

## [0.1.0] - 2025-07-28

### Added
- Initial release of Plan Manager.
- MCP server implementation for AI assistant integration.
- Task management with YAML-based storage (`todo/plan.yaml`).
- Dependency tracking and topological sorting.
- Priority-based task ordering (0-5 scale).
- Task status management (TODO, IN_PROGRESS, DONE, BLOCKED, DEFERRED).
- Archive functionality for completed tasks.
- CLI tools for direct task management:
  - `list_tasks.py` - List and filter tasks.
  - `show_task.py` - Display task details.
  - `update_task_status.py` - Update task status.
- Comprehensive logging system.
- Pydantic-based data validation.
- SSE transport support for MCP communication.
- Development container configuration.
- Comprehensive documentation and setup instructions.

### Features
- **Task Management**: Create, read, update, delete operations.
- **Dependency Management**: Define task dependencies with cycle detection.
- **Priority System**: 6-level priority system (0=highest, 5=lowest, null=no priority).
- **Status Tracking**: Five status types with validation.
- **Archive System**: Move completed tasks to archive with detail preservation.
- **AI Integration**: Full MCP server implementation for AI assistants.
- **Data Validation**: Robust schema validation using Pydantic models.
- **Logging**: Comprehensive logging to both files and stderr.
- **CLI Interface**: Direct command-line access to all functionality.

### Technical Details
- Python 3.11+ required.
- Built with FastMCP, Starlette, and Uvicorn.
- YAML-based data storage with backup/archive support.
- Type hints throughout codebase.
- Comprehensive error handling and validation.
