# Changelog

All notable changes to the Plan Manager project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.3] - 2025-08-26

### Changed
- SSE transport is replaced by Streamable HTTP
- Refactored application configuration to follow Twelve-Factor App principles. All settings are now sourced from environment variables with sensible defaults. Command-line arguments have been removed for simplicity.
- Configuration logic has been consolidated into the `plan_manager.config` module.
- The logging system has been unified. All modules now use a consistent, centrally configured logger that inherits its settings from the main entrypoint.
- Logging now defaults to writing to `stdout` as an event stream, adhering to Twelve-Factor principles. File-based logging is now an opt-in feature for development.

### Added
- The `PLAN_MANAGER_ENABLE_FILE_LOG` variable is now set in `.devcontainer/devcontainer.json` to automatically enable file logging for a better development experience.
- Added `logs/` directory to `.gitignore` to prevent log files from being committed.

### Fixed
- Suppressed ASGI app factory warning from Uvicorn by adding `factory=True` to the `uvicorn.run()` call.

## [0.2.2] - 2025-08-23

### Changed
- Refactor: split modules into `story_model.py`, `stories.py`, `plan.py`, `archive.py` for clarity.
- Explicit MCP tool registration (stories, plan, archive) from `mcp_server.py`.
- Cleaned imports, removed sys.path hacks, and fixed circular imports.

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
- Specialized `update_task_status_handler` and `update_task_priority_handler` in favor of `update_task`.

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
- Initial release of Plan Manager
- MCP server implementation for AI assistant integration
- Task management with YAML-based storage (`todo/plan.yaml`)
- Dependency tracking and topological sorting
- Priority-based task ordering (0-5 scale)
- Task status management (TODO, IN_PROGRESS, DONE, BLOCKED, DEFERRED)
- Archive functionality for completed tasks
- CLI tools for direct task management:
  - `list_tasks.py` - List and filter tasks
  - `show_task.py` - Display task details
  - `update_task_status.py` - Update task status
- Comprehensive logging system
- Pydantic-based data validation
- SSE transport support for MCP communication
- Development container configuration
- Comprehensive documentation and setup instructions

### Features
- **Task Management**: Create, read, update, delete operations
- **Dependency Management**: Define task dependencies with cycle detection
- **Priority System**: 6-level priority system (0=highest, 5=lowest, null=no priority)
- **Status Tracking**: Five status types with validation
- **Archive System**: Move completed tasks to archive with detail preservation
- **AI Integration**: Full MCP server implementation for AI assistants
- **Data Validation**: Robust schema validation using Pydantic models
- **Logging**: Comprehensive logging to both files and stderr
- **CLI Interface**: Direct command-line access to all functionality

### Technical Details
- Python 3.11+ required
- Built with FastMCP, Starlette, and Uvicorn
- YAML-based data storage with backup/archive support
- Type hints throughout codebase
- Comprehensive error handling and validation
