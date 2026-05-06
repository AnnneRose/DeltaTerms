"""Exponential backoff retries for Hugging Face Inference API rate limits (429).

Large evaluation runs issue many consecutive requests; the HF router returns
HTTP 429 when quotas are exceeded briefly. Retrying after a delay usually
succeeds without losing the whole suite."""

from __future__ import annotations

import os
import random
import time
from typing import Callable, TypeVar

T = TypeVar("T")


def _is_rate_limit(exc: BaseException) -> bool:
    msg = str(exc).lower()
    if "429" in msg or "too many requests" in msg:
        return True
    resp = getattr(exc, "response", None)
    code = getattr(resp, "status_code", None)
    return code == 429


def call_with_hf_retry(
    fn: Callable[[], T],
    *,
    max_attempts: int | None = None,
    base_delay_s: float = 2.0,
    max_delay_s: float = 120.0,
    label: str = "hf",
) -> T:
    """Run ``fn`` and retry on HTTP 429 with exponential backoff + jitter."""
    attempts = max_attempts
    if attempts is None:
        attempts = int(os.environ.get("HF_RETRY_MAX_ATTEMPTS", "8"))
    attempts = max(1, attempts)

    for attempt in range(1, attempts + 1):
        try:
            return fn()
        except BaseException as exc:
            if not _is_rate_limit(exc) or attempt >= attempts:
                raise
            delay = min(max_delay_s, base_delay_s * (2 ** (attempt - 1)))
            delay *= 0.8 + 0.4 * random.random()
            print(
                f"[{label}] rate limited; attempt {attempt}/{attempts}, "
                f"sleeping {delay:.1f}s ({type(exc).__name__})"
            )
            time.sleep(delay)
