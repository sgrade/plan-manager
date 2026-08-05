# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from typing import Any

import yaml


def split_front_matter(raw_text: str) -> tuple[dict[str, Any], str]:
    """Split markdown text containing YAML front matter into metadata and body."""
    if raw_text.startswith("---"):
        parts = raw_text.split("\n")
        if len(parts) > 1:
            try:
                end_index = None
                for i in range(1, len(parts)):
                    if parts[i].strip() == "---":
                        end_index = i
                        break
                if end_index is not None:
                    yaml_block = "\n".join(parts[1:end_index])
                    body = "\n".join(parts[end_index + 1 :])
                    front = yaml.safe_load(yaml_block) or {}
                    if not isinstance(front, dict):
                        front = {}
                    return front, body.lstrip("\n")
            except (yaml.YAMLError, ValueError, KeyError):
                pass
    return {}, raw_text


def render_with_front_matter(front: dict[str, Any], body: str) -> str:
    """Render a dictionary and body text into markdown with YAML front matter."""
    fm = yaml.safe_dump(front, sort_keys=False).rstrip() + "\n"
    return f"---\n{fm}---\n\n{body or ''}"
