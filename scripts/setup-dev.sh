#!/usr/bin/env bash
#
# setup-dev.sh — one-time setup for a fresh clone. Safe to re-run.
#
# The devcontainer runs this via postCreateCommand; run it by hand if you work
# outside the container.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

# Local gates live in .githooks/: pre-commit chains the pre-commit framework,
# pre-push runs scripts/verify.sh. Git ignores that directory unless it is
# pointed there, so without this line a fresh clone has NO local verification
# and mistakes surface only once CI runs.
git config core.hooksPath .githooks

uv sync --all-extras --dev
uv run pre-commit install-hooks

# The container inherits the host's ~/.gitconfig, whose host-specific entries
# point at a macOS path (/opt/homebrew/bin/gh) that does not exist here, so
# every push prints two errors before falling back. `|| true` because unsetting
# an absent key exits 5, which would abort this script.
git config --global --unset-all 'credential.https://github.com.helper' || true
git config --global --unset-all 'credential.https://gist.github.com.helper' || true
git config --global credential.helper '!/usr/bin/gh auth git-credential'
