#!/usr/bin/env bash
#
# verify.sh — the canonical verification gate.
#
# One definition of every check, three callers:
#
#   .githooks/pre-push       ./scripts/verify.sh          (everything, ~5s)
#   .github/workflows/*.yml  ./scripts/verify.sh <stage>  (one stage per job)
#   you, any time            ./scripts/verify.sh
#
# Local hooks are a convenience and are bypassable (`git push --no-verify`);
# CI is the enforceable gate. They run the same commands from this file so the
# two can never disagree — a past incident had local mypy and CI mypy reaching
# opposite conclusions about the same code.
#
# Stages exist so the CI jobs keep their own names (they are required status
# checks on main) without CI restating the commands.

set -euo pipefail

cd "$(git rev-parse --show-toplevel)"

lint() {
    uv run ruff check src/ tests/
    uv run ruff format --check src/ tests/
}

types() {
    uv run mypy src/plan_manager --no-error-summary
}

security() {
    # bandit emits a false "nosec encountered ... but no failed test" line for
    # every f-string interpolation under a `# nosec Bxxx` (PyCQA/bandit#1204,
    # still unfixed in 1.9.4, the latest release). Drop only that message.
    # REMOVE THIS FILTER once the upstream fix ships: the message then becomes a
    # real signal that a suppression has gone stale.
    # Output is captured rather than piped so bandit's exit code survives, and
    # `|| status=$?` is required: under `set -e` a bare assignment from a failing
    # command substitution aborts the function before the findings are printed.
    local output status=0
    output=$(uv run bandit -c pyproject.toml -r src/plan_manager -q 2>&1) || status=$?
    printf '%s' "$output" | grep -v "nosec encountered" || true
    return "$status"
}

tests() {
    # Coverage reports are written unconditionally: xml feeds Codecov and html
    # is uploaded as an artifact in CI, and both are gitignored locally.
    uv run pytest \
        --cov=src/plan_manager \
        --cov-report=xml \
        --cov-report=html \
        --cov-fail-under=40
}

build() {
    uv build
    uv run twine check dist/*
}

case "${1:-all}" in
    lint | types | security | tests | build) "$1" ;;
    # Sequenced with `;`, never `&&`: bash suspends `set -e` inside a function
    # that is part of an && list, so a failing first command in any stage would
    # be masked by a passing last one.
    all)
        lint
        types
        security
        tests
        build
        ;;
    *)
        echo "usage: ${0##*/} [lint|types|security|tests|build|all]" >&2
        exit 2
        ;;
esac
