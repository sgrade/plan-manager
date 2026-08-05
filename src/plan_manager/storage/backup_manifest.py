# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

"""Backup manifest helpers shared by export/import flows."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

MANIFEST_FILENAME = "MANIFEST"
MANIFEST_VERSION = 1


def compute_tree_content_hash(root: Path) -> str:
    """Compute a stable hash across every file except MANIFEST."""
    digest = hashlib.sha256()
    files = sorted(
        file_path
        for file_path in root.rglob("*")
        if file_path.is_file() and file_path.name != MANIFEST_FILENAME
    )
    for file_path in files:
        relative = file_path.relative_to(root).as_posix().encode("utf-8")
        content = file_path.read_bytes()
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(content)
    return digest.hexdigest()
