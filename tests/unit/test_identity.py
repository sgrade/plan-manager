# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import json
import os
import subprocess
import sys
from importlib import metadata
from pathlib import Path

from plan_manager import identity

_REVISION = "a" * 40


def test_identity_uses_installed_version_and_packaged_revision(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "_build_identity.json").write_text(
        json.dumps({"source_revision": _REVISION}) + "\n"
    )
    monkeypatch.setattr(identity.metadata, "version", lambda _name: "1.2.3")
    monkeypatch.setattr(identity.resources, "files", lambda _name: tmp_path)

    assert identity.build_identity() == {
        "product": "plan-manager",
        "product_version": "1.2.3",
        "source_revision": _REVISION,
    }
    assert identity.build_identity_json() == (
        '{"product": "plan-manager", "product_version": "1.2.3", '
        f'"source_revision": "{_REVISION}"}}\n'
    )
    assert identity.version_line() == (
        f"plan-manager product_version=1.2.3 source_revision={_REVISION}"
    )


def test_identity_reports_unknown_when_metadata_is_unavailable(
    tmp_path: Path, monkeypatch
) -> None:
    def missing_version(_name: str) -> str:
        raise metadata.PackageNotFoundError

    monkeypatch.setattr(identity.metadata, "version", missing_version)
    monkeypatch.setattr(identity.resources, "files", lambda _name: tmp_path)

    assert identity.build_identity() == {
        "product": "plan-manager",
        "product_version": "unknown",
        "source_revision": "unknown",
    }


def test_malformed_packaged_revision_reports_unknown(
    tmp_path: Path, monkeypatch
) -> None:
    (tmp_path / "_build_identity.json").write_text(
        '{"source_revision": "not-a-commit"}\n'
    )
    monkeypatch.setattr(identity.resources, "files", lambda _name: tmp_path)

    assert identity.source_revision() == "unknown"


def test_cli_version_stays_on_one_line_in_narrow_terminal() -> None:
    env = dict(os.environ)
    env["COLUMNS"] = "40"

    result = subprocess.run(
        [sys.executable, "-m", "plan_manager", "--version"],
        cwd=Path(__file__).resolve().parents[2],
        env=env,
        check=True,
        text=True,
        capture_output=True,
    )

    assert result.stderr == ""
    assert result.stdout.count("\n") == 1
    assert result.stdout.startswith("plan-manager product_version=")
    assert " source_revision=" in result.stdout
