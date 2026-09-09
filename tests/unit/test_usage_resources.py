# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import logging
from pathlib import Path

from plan_manager.resources import usage_resources


class _FakeMCP:
    def __init__(self) -> None:
        self.handlers = {}

    def resource(self, **metadata):
        def decorate(function):
            self.handlers[metadata["uri"]] = function
            return function

        return decorate


def test_packaged_guide_is_preferred_and_returned_exactly(
    tmp_path: Path, monkeypatch
) -> None:
    package = tmp_path / "package"
    docs = package / "docs"
    docs.mkdir(parents=True)
    (docs / "guide.md").write_text("packaged guide\n")
    development = tmp_path / "development.md"
    development.write_text("development guide\n")
    monkeypatch.setattr(usage_resources, "files", lambda _package: package)

    result = usage_resources._read_guide(  # noqa: SLF001
        filename="guide.md",
        development_path=str(development),
        override_path=None,
        env_name="GUIDE_PATH",
        title="Guide",
    )

    assert result == "packaged guide\n"


def test_explicit_override_wins(tmp_path: Path) -> None:
    override = tmp_path / "override.md"
    override.write_text("override guide\n")

    result = usage_resources._read_guide(  # noqa: SLF001
        filename="missing.md",
        development_path="also-missing.md",
        override_path=str(override),
        env_name="GUIDE_PATH",
        title="Guide",
    )

    assert result == "override guide\n"


def test_missing_override_degrades_without_default_fallback(
    tmp_path: Path, caplog
) -> None:
    development = tmp_path / "development.md"
    development.write_text("must not be used\n")

    with caplog.at_level(logging.WARNING):
        result = usage_resources._read_guide(  # noqa: SLF001
            filename="guide.md",
            development_path=str(development),
            override_path=str(tmp_path / "missing.md"),
            env_name="GUIDE_PATH",
            title="Guide",
        )

    assert result == (
        "# Plan Manager — Guide\n\n"
        "Guide content is unavailable. Check or unset GUIDE_PATH "
        "and restart Plan Manager.\n"
    )
    assert "guide.md guide content is unavailable" in caplog.text


def test_missing_package_uses_development_fallback(tmp_path: Path, monkeypatch) -> None:
    development = tmp_path / "development.md"
    development.write_text("development guide\n")
    monkeypatch.setattr(
        usage_resources,
        "files",
        lambda _package: tmp_path / "missing-package",
    )

    result = usage_resources._read_guide(  # noqa: SLF001
        filename="guide.md",
        development_path=str(development),
        override_path=None,
        env_name="GUIDE_PATH",
        title="Guide",
    )

    assert result == "development guide\n"


def test_all_resources_are_registered(monkeypatch) -> None:
    fake = _FakeMCP()
    monkeypatch.setattr(
        usage_resources,
        "build_identity_json",
        lambda: '{"product":"plan-manager"}\n',
    )

    usage_resources.register_usage_resources(fake)

    assert set(fake.handlers) == {
        "resource://plan-manager/usage_guide_agents.md",
        "resource://plan-manager/project_workflow.md",
        "resource://plan-manager/build_info.json",
    }
    assert (
        fake.handlers["resource://plan-manager/build_info.json"]()
        == '{"product":"plan-manager"}\n'
    )
