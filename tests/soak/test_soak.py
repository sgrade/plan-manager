# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Pytest entry for the concurrency soak harness.

Marked ``soak`` and excluded from the default run via
``tests/soak/conftest.py``. Invoke explicitly:

    uv run pytest -m soak tests/soak/

Durations and client counts are env-tunable via ``tests/soak/soak_harness.py``.
The harness asserts its own pass criteria and writes a verdict report to
``tmp/stability-and-multiplan/reviews/u9-soak-report.md``; this test fails the
pytest run if the harness verdict is not ``pass``.
"""

import pytest
from soak_harness import run_soak

pytestmark = pytest.mark.soak


@pytest.mark.soak
def test_soak() -> None:
    result = run_soak()
    overall = result["overall"]
    msg = (
        f"soak verdict={overall}; total_calls={result['total_calls']}; "
        f"outcomes={result['outcome_counts']}; races={result['races']} "
        f"(bad={result['bad_races']}); report={result['report_path']}"
    )
    if overall != "pass":
        pytest.fail(msg)
