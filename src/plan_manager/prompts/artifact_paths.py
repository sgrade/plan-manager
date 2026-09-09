# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from pathlib import PurePosixPath
from uuid import uuid4


def prompt_artifact_path(filename: str) -> str:
    """Return an invocation-unique, consumer-local proposal path."""
    return str(PurePosixPath(".plan-manager-tmp") / uuid4().hex / filename)


def authority_instructions(action: str, artifact_path: str) -> str:
    """Describe caller-held authority without claiming PM enforcement."""
    parent = str(PurePosixPath(artifact_path).parent)
    return (
        f"If authority already recorded in your governing context covers {action}, "
        "continue without requesting the same approval again. "
        f"After the proposal is consumed, delete only '{parent}'. "
        "If authority is absent, exhausted, out of scope, or the decision is "
        "reserved, preserve the proposal and surface only that missing or "
        "reserved decision. Plan Manager reports workflow state; it does not "
        "grant or verify authority."
    )
