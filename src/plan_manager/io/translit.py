# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

# ruff: noqa: RUF001  -- the keys of this table ARE Cyrillic letters on purpose
"""Cyrillic transliteration for filesystem-safe slugs.

Titles in Russian used to slugify to an empty string because ``slugify`` keeps
only ``a-z0-9``. This table gives such titles a stable ASCII representation, so
an item can never end up with an empty id.
"""

CYRILLIC_TO_LATIN: dict[str, str] = {
    "а": "a",
    "б": "b",
    "в": "v",
    "г": "g",
    "д": "d",
    "е": "e",
    "ё": "e",
    "ж": "zh",
    "з": "z",
    "и": "i",
    "й": "y",
    "к": "k",
    "л": "l",
    "м": "m",
    "н": "n",
    "о": "o",
    "п": "p",
    "р": "r",
    "с": "s",
    "т": "t",
    "у": "u",
    "ф": "f",
    "х": "kh",
    "ц": "ts",
    "ч": "ch",
    "ш": "sh",
    "щ": "sch",
    "ъ": "",
    "ы": "y",
    "ь": "",
    "э": "e",
    "ю": "yu",
    "я": "ya",
    # Ukrainian and Belarusian letters
    "і": "i",
    "ї": "yi",
    "є": "ye",
    "ґ": "g",
    "ў": "u",
}


def build_transliteration_table() -> dict[int, str]:
    """Return a ``str.translate`` table for both letter cases."""
    table = {ord(char): latin for char, latin in CYRILLIC_TO_LATIN.items()}
    table.update(
        {ord(char.upper()): latin for char, latin in CYRILLIC_TO_LATIN.items()}
    )
    return table
