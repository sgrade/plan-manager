# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import os
import subprocess
from pathlib import Path


def test_build_rejects_malformed_source_revision(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    env = dict(os.environ)
    env["PLAN_MANAGER_SOURCE_REVISION"] = "not-a-full-commit"

    result = subprocess.run(
        ["uv", "build", "--wheel", "--out-dir", str(tmp_path)],
        cwd=root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert "full lowercase 40-hex Git commit" in result.stderr
