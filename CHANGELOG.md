# Changelog

All notable changes to the Plan Manager project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## Removed
- Remove unnecessary commands (select_first_unblocked_task, advance_to_next_task, and get_current_context).

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
