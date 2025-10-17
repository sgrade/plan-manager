import logging
import random
import time
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from plan_manager.config import TELEMETRY_ENABLED, TELEMETRY_SAMPLE_RATE

logger = logging.getLogger(__name__)


def _should_sample() -> bool:
    """Determine if telemetry should be sampled based on configuration.

    Returns:
        bool: True if telemetry should be recorded for this operation
    """
    if not TELEMETRY_ENABLED:
        return False
    try:
        return random.random() < max(  # nosec B311  # Non-cryptographic sampling
            0.0, min(1.0, TELEMETRY_SAMPLE_RATE)
        )
    except (TypeError, ValueError):
        # Handle invalid TELEMETRY_SAMPLE_RATE values gracefully
        return False


def incr(metric: str, value: int = 1, **labels: Any) -> None:
    """Increment a counter metric.

    Args:
        metric: The metric name
        value: The value to increment by (default: 1)
        **labels: Additional key-value labels for the metric
    """
    if not _should_sample():
        return

    # Log telemetry data at debug level for production monitoring
    telemetry_data: dict[str, Any] = {
        "metric": metric,
        "type": "counter",
        "value": value,
        **labels,
    }
    logger.debug("Telemetry counter: %s", telemetry_data)


@contextmanager
def timer(metric: str, **labels: Any) -> Generator[None, None, None]:
    """Context manager for timing operations.

    Args:
        metric: The metric name for timing
        **labels: Additional key-value labels for the metric
    """
    if not _should_sample():
        yield
        return

    start = time.perf_counter()
    try:
        yield
    finally:
        dur_ms = (time.perf_counter() - start) * 1000.0
        telemetry_data = {
            "metric": metric,
            "type": "timer",
            "ms": round(dur_ms, 2),
            **labels,
        }
        logger.debug("Telemetry timer: %s", telemetry_data)
