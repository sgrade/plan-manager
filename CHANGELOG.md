# Changelog

All notable changes to the Plan Manager project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed
- Development workflow: document SSE-only setup with `uvicorn --reload` and a short graceful shutdown timeout.
- Added CLI flags for reload directories, include/exclude patterns, and timeouts.
- Guarded file logging behind `PLAN_MANAGER_ENABLE_FILE_LOG` to avoid reload-triggered churn during development.
- Polished README for SSE configuration and Cursor setup.

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
