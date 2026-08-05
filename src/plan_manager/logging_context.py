# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Roman Klyuev

from contextvars import ContextVar

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: str | None) -> None:
    """Set the correlation ID for the current request context.

    Args:
        value: The correlation ID string, or None to clear it
    """
    _correlation_id.set(value)


def get_correlation_id() -> str | None:
    """Get the correlation ID from the current request context.

    Returns:
        Optional[str]: The correlation ID if set, None otherwise
    """
    return _correlation_id.get()
