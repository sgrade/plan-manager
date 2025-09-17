from contextvars import ContextVar
from typing import Optional


_correlation_id: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None)


def set_correlation_id(value: Optional[str]) -> None:
    _correlation_id.set(value)


def get_correlation_id() -> Optional[str]:
    return _correlation_id.get()
