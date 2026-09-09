# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Runtime identity sourced only from installed package data."""

import json
import re
from importlib import metadata, resources

_FULL_REVISION = re.compile(r"^[0-9a-f]{40}$")


def product_version() -> str:
    """Return installed Plan Manager version or an honest unknown marker."""
    try:
        return metadata.version("plan-manager")
    except metadata.PackageNotFoundError:
        return "unknown"


def source_revision() -> str:
    """Return immutable packaged source revision or unknown."""
    try:
        raw = (
            resources.files("plan_manager")
            .joinpath("_build_identity.json")
            .read_text(encoding="utf-8")
        )
        value = json.loads(raw).get("source_revision")
    except (OSError, TypeError, ValueError):
        return "unknown"
    if value == "unknown":
        return "unknown"
    if isinstance(value, str) and _FULL_REVISION.fullmatch(value):
        return value
    return "unknown"


def build_identity() -> dict[str, str]:
    """Return the canonical product/source identity object."""
    return {
        "product": "plan-manager",
        "product_version": product_version(),
        "source_revision": source_revision(),
    }


def build_identity_json() -> str:
    """Serialize the canonical identity for MCP machine consumers."""
    return json.dumps(build_identity(), sort_keys=True) + "\n"


def version_line() -> str:
    """Render the stable operator-facing CLI identity."""
    identity = build_identity()
    return (
        f"plan-manager product_version={identity['product_version']} "
        f"source_revision={identity['source_revision']}"
    )
