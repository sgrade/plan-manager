import random
import time
from contextlib import contextmanager

from plan_manager.config import TELEMETRY_ENABLED, TELEMETRY_SAMPLE_RATE


def _should_sample() -> bool:
    if not TELEMETRY_ENABLED:
        return False
    try:
        return random.random() < max(0.0, min(1.0, TELEMETRY_SAMPLE_RATE))
    except Exception:
        return False


def incr(metric: str, value: int = 1, **labels) -> None:
    if not _should_sample():
        return
    # For now print to stdout; can be replaced with real sink later
    print({"metric": metric, "type": "counter", "value": value, **labels})


@contextmanager
def timer(metric: str, **labels):
    if not _should_sample():
        yield
        return
    start = time.perf_counter()
    try:
        yield
    finally:
        dur_ms = (time.perf_counter() - start) * 1000.0
        print({"metric": metric, "type": "timer",
              "ms": round(dur_ms, 2), **labels})
