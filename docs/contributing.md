# Contributing

This document guides human contributors to this repository.

## Core guidelines

Keep the server simple: tools enforce workflow; prompts are convenience only; roots/elicitation are client-side.

## Conventions

Commit messages: [https://www.conventionalcommits.org](https://www.conventionalcommits.org)

Semantic Versioning: [https://semver.org](https://semver.org)

Changelog: [https://keepachangelog.com](https://keepachangelog.com)

## Triage

Refer to the Triage Guide for labels, severity definitions, SLAs, and routine:
see [triage_guide.md](./triage_guide.md).

For agent usage guidance (when Plan Manager is used as a service in other projects), see `AGENTS.md` at the repo root.

## Development Environment

This project is configured to run inside a [Dev Container](https://containers.dev/).

**Automatic Installation**: The dev container is configured to automatically install all necessary Python dependencies using `uv` when it's built for the first time. This is handled by the `postCreateCommand` in `.devcontainer/devcontainer.json`.

### Running the Server

Once the dev container is running, start the MCP server from the VS Code terminal:

```bash
uv run pm
```

The server will start on `http://localhost:3000/mcp`.

Automatic server reload for the dev environment is configured in the `devcontainer.json` by setting `PLAN_MANAGER_RELOAD` to `true`.

Note: After MCP server is reloaded, Cursor (the client) does not reconnect automatically. To make Cursor reconnect, flip the MCP server switch in Cursor settings to off, then on.

### Configuration for Cursor IDE

To allow Cursor to communicate with this server, ensure your global `.cursor/mcp.json` file has an entry like this:

```json
{
  "mcpServers": {
      "plan-manager": {
        "url": "http://localhost:3000/mcp"
      }
  }
}
```

If accessing from another Cursor instance (devcontainer) on the same host, point to the Docker-host bridge DNS:

```json
{
  "mcpServers": {
    "plan-manager": {
      "url": "http://host.docker.internal:3000/mcp"
    }
  }
}
```

### Testing the Server

You can verify that the server is running by sending requests to its endpoints:

```bash
# This should return a 404 Not Found, which is expected.
curl -i http://localhost:3000/
```

This is expected because the root path has no route.

A JSON response is expected on the below request.

Note: jq is required for the below to work.

```bash
curl -sN \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  --data '{
    "jsonrpc":"2.0",
    "id":1,
    "method":"initialize",
    "params":{
      "protocolVersion":"2025-03-26",
      "capabilities":{},
      "clientInfo":{"name":"curl","version":"0"}
    }
  }' \
  http://localhost:3000/mcp \
| sed -n 's/^data: //p' \
| jq
```

To test with MCP-Inspector, check [../dev/mcp-inspector/README.md](../dev/mcp-inspector/README.md)

### Running Tests

**Test Isolation**: All tests run in isolated temp directories (via `tests/conftest.py` autouse fixture). Your real `todo/` directory is never touched.

```bash
# All tests
uv run pytest

# Unit tests only (fastest, ~3s)
uv run pytest tests/unit/

# Integration tests only
uv run pytest -m integration

# With coverage
uv run pytest --cov=src/plan_manager --cov-report=html
open htmlcov/index.html
```

**Test Structure**:
- `tests/unit/` - Fast isolated tests (domain models, validation, utilities)
- `tests/integration/` - Tests with filesystem (story/task workflows)
- `tests/conftest.py` - Auto-isolation fixture (redirects TODO_DIR to temp)

### Logging

-   **Terminal Output**: By default the logs are written to stdout as [recommended](https://12factor.net/logs).
-   **Log file**: If you need the logs in a file, set `PLAN_MANAGER_ENABLE_FILE_LOG` to `true` in the devcontainer.json. The server's detailed application logs will be written to `logs/mcp_server_app.log` (configurable).

## Configuration Reference

See [config_reference.md](./config_reference.md) for all environment variables, defaults, and examples.

## Release Process

This project uses [release-please](https://github.com/googleapis/release-please) to automate releases based on [Conventional Commits](https://www.conventionalcommits.org/).

### How It Works

1. **Commit your changes** using conventional commit messages:
   ```bash
   git commit -m "feat: add new amazing feature"
   git commit -m "fix: resolve critical bug"
   git commit -m "docs: update documentation"
   ```

2. **Merge to main** (via develop or direct):
   ```bash
   git checkout main
   git merge develop
   git push origin main
   ```

3. **Release-please automatically**:
   - Analyzes commits since last release
   - Determines version bump (major/minor/patch) based on commit types
   - Creates a "Release PR" with:
     - Updated `CHANGELOG.md`
     - Bumped version in `pyproject.toml`
     - Updated `.release-please-manifest.json`

4. **Review and merge the Release PR**:
   - Check the version bump is appropriate
   - Verify the changelog entries are accurate
   - Merge the PR on GitHub

5. **Automatic release**:
   - Release-please creates a git tag (e.g., `v0.10.0`)
   - Creates a GitHub Release with release notes
   - CI workflow builds and uploads distribution artifacts

### Commit Message Format

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` - New feature (bumps minor version: 0.9.0 → 0.10.0)
- `fix:` - Bug fix (bumps patch version: 0.9.0 → 0.9.1)
- `docs:` - Documentation only (no version bump)
- `chore:` - Maintenance tasks (no version bump)
- `refactor:` - Code refactoring (no version bump)
- `perf:` - Performance improvements (no version bump)
- `test:` - Test changes (no version bump)
- `BREAKING CHANGE:` - Breaking change (bumps major version: 0.9.0 → 1.0.0)

### Emergency Manual Release

In exceptional circumstances (e.g., critical hotfix when CI is down, or need to release from a fork), manual release steps are documented in [release_checklist.md](./release_checklist.md).

## Quality Gates

See [release_checklist.md](./release_checklist.md) for pre-release quality checks and verification steps.
