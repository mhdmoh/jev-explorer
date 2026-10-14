"""Simple timing helpers."""

from __future__ import annotations

import time


class Timer:
    """Context manager measuring elapsed milliseconds."""

    def __init__(self) -> None:
        self.started = 0.0
        self.elapsed_ms = 0.0

    def __enter__(self) -> Timer:
        self.started = time.perf_counter()
        return self

    def __exit__(self, *args: object) -> None:
        self.elapsed_ms = (time.perf_counter() - self.started) * 1000
