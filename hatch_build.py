# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Generate immutable source identity inside built wheels."""

import json
import os
import re
import shutil
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

_FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")


def source_revision() -> str:
    """Validate the build-only source revision."""
    revision = os.getenv("PLAN_MANAGER_SOURCE_REVISION") or "unknown"
    if revision != "unknown" and _FULL_REVISION.fullmatch(revision) is None:
        raise ValueError(
            "PLAN_MANAGER_SOURCE_REVISION must be a full lowercase 40-hex Git commit"
        )
    return revision


class CustomBuildHook(BuildHookInterface):
    """Embed a verified source revision or an honest unknown marker."""

    PLUGIN_NAME = "custom"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        _ = version
        revision = source_revision()

        generated_dir = Path(self.directory) / "plan-manager-build-identity"
        generated_dir.mkdir(parents=True, exist_ok=True)
        generated = generated_dir / "_build_identity.json"
        generated.write_text(
            json.dumps({"source_revision": revision}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        build_data.setdefault("force_include", {})[str(generated)] = (
            "plan_manager/_build_identity.json"
        )

    def finalize(
        self,
        version: str,
        build_data: dict[str, Any],
        artifact_path: str,
    ) -> None:
        _ = version, build_data, artifact_path
        shutil.rmtree(
            Path(self.directory) / "plan-manager-build-identity",
            ignore_errors=True,
        )
