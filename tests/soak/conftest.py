# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Soak harness collection guard.

The soak harness spins up a real `pm` server subprocess and drives it with
tens of concurrent MCP clients for several minutes. It must never run as part
of the default `uv run pytest` invocation. pytest's `-m soak` selector is the
documented entry point; we detect it by inspecting the marker expression and
skip every item in this directory otherwise.
"""

import pytest


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    markexpr = config.option.markexpr or ""
    soak_selected = "soak" in markexpr
    if soak_selected:
        return
    skip = pytest.mark.skip(
        reason="soak harness excluded from default run; invoke with `pytest -m soak`"
    )
    for item in items:
        # Only skip items that live in the soak directory.
        if "tests/soak" in str(item.fspath).replace("\\", "/"):
            item.add_marker(skip)
