# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

import re


def slugify(title: str) -> str:
    """Convert a title into a URL-safe slug.

    Args:
        title: The title to convert

    Returns:
        str: The slugified version with lowercase letters, numbers, and underscores

    Raises:
        ValueError: If title is empty
    """
    if not title:
        raise ValueError("Title cannot be empty when generating a slug.")
    s = title.lower()
    s = re.sub(r"[^a-z0-9\s]+", " ", s)
    return re.sub(r"\s+", "_", s.strip())
