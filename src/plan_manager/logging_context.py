from contextvars import ContextVar
from typing import Optional

_correlation_id: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


def set_correlation_id(value: Optional[str]) -> None:
    """Set the correlation ID for the current request context.

    Args:
        value: The correlation ID string, or None to clear it
    """
    _correlation_id.set(value)


def get_correlation_id() -> Optional[str]:
    """Get the correlation ID from the current request context.

    Returns:
        Optional[str]: The correlation ID if set, None otherwise
    """
    return _correlation_id.get()
