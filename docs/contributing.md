# Contributing

This document guides human contributors to this repository.

## Core guidelines

Keep the server simple: tools enforce workflow; prompts are convenience only; roots/elicitation are client-side.

## Conventions

Commit messages: [https://www.conventionalcommits.org](https://www.conventionalcommits.org)

Semantic Versioning: [https://semver.org](https://semver.org)

Changelog: [https://keepachangelog.com](https://keepachangelog.com)

## Branching Strategy

This project follows a simplified Git Flow:

### Normal Development

Granularity mirrors the plan vocabulary: **a task is a commit, a story is a
push, an epic is a merge to `main`.** Commit small conventional commits and do
not squash them before pushing — release-please builds the changelog from them.
Individual commits need not be green (the gate runs at push time), so prefer
`git bisect --first-parent` when hunting a regression.

**Work on `develop` branch:**
```bash
git checkout develop
git commit -m "feat: add new feature"
git commit -m "fix: resolve bug"
git push origin develop   # pre-push runs the full gate
```

**When ready to release:**
```bash
# Merge develop to main. --ff-only is what makes main trustworthy: the commit
# landing on main is the identical SHA CI already verified on develop, so it
# arrives carrying green checks. A squash or merge commit would be a new,
# never-verified SHA and would collapse the conventional commits.
git checkout main
git merge --ff-only develop
git push origin main

# Release-please will automatically:
# 1. Create a Release PR
# 2. Update version and changelog
# You then review and merge the Release PR
```

### Emergency Hotfixes

For critical production issues (P0) that can't wait for the normal release cycle:

**Option 1: Hotfix branch from main**
```bash
# Create hotfix branch from main
git checkout -b hotfix/critical-security-fix main

# Fix the issue
git commit -m "fix: critical security vulnerability in authentication"

# Merge to main
git checkout main
git merge hotfix/critical-security-fix
git push origin main

# Merge back to develop to keep in sync
git checkout develop
git merge hotfix/critical-security-fix
git push origin develop
```

**Option 2: Direct commit to main (extreme emergency only)**
```bash
# Only when CI is down or immediate release required
git checkout main
git commit -m "fix: critical data loss bug"
git push origin main

# Don't forget to merge back to develop
git checkout develop
git merge main
git push origin develop
```

**Always:** Ensure hotfixes are merged back to `develop` to keep branches in sync.

### Branch Protection

The `main` branch should be protected with these settings:
- Require pull request before merging (exceptions: hotfixes, release-please)
- Require status checks to pass (CI, tests, lint)
- Require branches to be up to date before merging

See [GitHub Branch Protection](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches) for setup instructions.

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

### Verification gates

`scripts/verify.sh` is the single definition of every check. It runs in about
seven seconds and is invoked from three places, so they cannot drift apart:

```bash
./scripts/verify.sh          # everything: lint, types, security, tests, build
./scripts/verify.sh types    # one stage; CI jobs call it this way
```

- **Commit** (`.githooks/pre-commit`): signing identity, content hygiene, and
  ruff on staged files only. Kept under a second so it is never bypassed.
- **Push** (`.githooks/pre-push`): the full gate. This is the local control.
- **CI**: the same gate on a clean checkout. Local hooks are bypassable with
  `--no-verify`, so CI is the enforceable one, and on `develop` it is also the
  real pre-merge gate — see the `--ff-only` note above.

Both hooks live in `.githooks/`, which git only consults once `core.hooksPath`
points there. The devcontainer does this for you on creation; outside it, run
`./scripts/setup-dev.sh` once per clone. Until then a clone has no local gate
at all, and CI is the first thing that will tell you something is wrong.

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
   git merge --ff-only develop
   git push origin main
   ```
   `--ff-only` fails loudly if the branches have diverged instead of creating a
   surprise merge commit. If it fails, sync `main` back into `develop` first.

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
   - Squash-merge with an admin bypass:
     ```bash
     gh pr merge <pr> --squash --admin
     ```
     release-please commits through the git data API, which GitHub does not sign,
     so the `main` ruleset (`required_signatures`) refuses the merge without a
     bypass — every merge method is refused, not just this one. Squashing means
     the unsigned commit is discarded and what lands on `main` is a fresh commit
     GitHub signs itself, so the branch history stays fully verified.

5. **Automatic release**:
   - Release-please creates a git tag (e.g., `plan-manager-v0.13.0`)
   - Creates a GitHub Release with release notes
   - The `Release` workflow builds the distribution for that tag and attaches it
     to the release. To backfill artifacts for an existing tag, dispatch it
     manually: `gh workflow run release.yml -f tag=plan-manager-v0.13.0`

6. **Refresh the lockfile** on `develop`: release-please bumps the version in
   `pyproject.toml` only, so run `uv lock` and commit the resulting
   `plan-manager` version bump in `uv.lock`. Otherwise the next `uv run` dirties
   the working tree for everyone.

### Commit Message Format

Follow the [Conventional Commits](https://www.conventionalcommits.org/) specification:

- `feat:` - New feature (bumps minor version: 0.9.0 → 0.10.0)
- `fix:` - Bug fix (bumps patch version: 0.9.0 → 0.9.1)
- `docs:` - Documentation only (no version bump)
- `chore:` - Maintenance tasks (no version bump)
- `refactor:` - Code refactoring (no version bump)
- `perf:` - Performance improvements (no version bump)
- `test:` - Test changes (no version bump)
- `BREAKING CHANGE:` (or `feat!:`) - Breaking change. Pre-1.0 this bumps the
  minor version (0.12.0 → 0.13.0), because `bump-minor-pre-major` is enabled in
  `release-please-config.json`; it will bump major only after 1.0.0.

### Emergency Manual Release

In exceptional circumstances (e.g., critical hotfix when CI is down, or need to release from a fork), manual release steps are documented in [release_checklist.md](./release_checklist.md).

## Quality Gates

See [release_checklist.md](./release_checklist.md) for pre-release quality checks and verification steps.
