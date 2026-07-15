"""Small, synchronous resilience primitives for external model providers."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Callable, TypeVar

T = TypeVar("T")


class CircuitOpenError(RuntimeError):
    """Raised when a provider circuit is cooling down after repeated failures."""


PROVIDER_UNAVAILABLE_MESSAGE = (
    "Dịch vụ AI đang tạm thời gián đoạn. Workspace của anh/chị vẫn được giữ nguyên; "
    "vui lòng thử lại sau ít phút hoặc tiếp tục bằng các bước form hiện có."
)


@dataclass(frozen=True)
class ProviderResult:
    value: object
    provider: str


def is_retryable_provider_error(error: Exception) -> bool:
    """Return true only for transient transport, throttling, and server errors."""
    status = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    if status == 429 or (isinstance(status, int) and status >= 500):
        return True
    if isinstance(status, int):
        return False

    name = type(error).__name__.lower()
    message = str(error).lower()
    transient_markers = (
        "timeout", "timed out", "connection", "connecterror", "network",
        "temporarily unavailable", "service unavailable", "rate limit",
    )
    return any(marker in name or marker in message for marker in transient_markers)


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, cooldown_seconds: float = 30.0):
        self.failure_threshold = max(1, failure_threshold)
        self.cooldown_seconds = max(0.0, cooldown_seconds)
        self._failures = 0
        self._opened_at: float | None = None
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        with self._lock:
            if self._opened_at is None:
                return False
            if time.monotonic() - self._opened_at >= self.cooldown_seconds:
                self._opened_at = None
                self._failures = 0
                return False
            return True

    def call(self, operation: Callable[[], T]) -> T:
        if self.is_open:
            raise CircuitOpenError("model provider circuit is open")
        try:
            result = operation()
        except Exception as error:
            if is_retryable_provider_error(error):
                with self._lock:
                    self._failures += 1
                    if self._failures >= self.failure_threshold:
                        self._opened_at = time.monotonic()
            raise
        with self._lock:
            self._failures = 0
            self._opened_at = None
        return result

    def reset(self) -> None:
        with self._lock:
            self._failures = 0
            self._opened_at = None


def execute_with_fallback(
    primary: Callable[[], T],
    breaker: CircuitBreaker,
    fallback: Callable[[], T] | None = None,
) -> tuple[T, str]:
    """Run primary and use fallback only for transient/open-circuit failures."""
    try:
        return breaker.call(primary), "primary"
    except Exception as error:
        if fallback is None or not (
            isinstance(error, CircuitOpenError) or is_retryable_provider_error(error)
        ):
            raise
        return fallback(), "fallback"
