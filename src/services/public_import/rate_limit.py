from __future__ import annotations
import time
from threading import Lock
from .errors import RateLimitedError
_last = {}; _lock = Lock()
def enforce(provider: str, interval: float = 1.0):
    with _lock:
        now = time.monotonic()
        if now - _last.get(provider, 0) < interval: raise RateLimitedError()
        _last[provider] = now
