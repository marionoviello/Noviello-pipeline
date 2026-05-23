"""Decorador de retry exponencial para chamadas httpx (3x: 2s/8s/32s)."""

from __future__ import annotations

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

_STATUS_TRANSITORIOS = {429, 500, 502, 503, 504}


def _transitorio(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in _STATUS_TRANSITORIOS
    return isinstance(exc, (httpx.TimeoutException, httpx.TransportError))


transient_retry = retry(
    retry=retry_if_exception(_transitorio),
    wait=wait_exponential(multiplier=2, min=2, max=32),
    stop=stop_after_attempt(3),
    reraise=True,
)
