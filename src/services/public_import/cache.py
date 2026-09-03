from __future__ import annotations

import time
from collections import OrderedDict
from threading import Lock
from typing import Generic, TypeVar

from src.config import settings


T = TypeVar("T")


class TTLCache(Generic[T]):
    """Small process-local LRU cache; it never writes cases or other files."""

    def __init__(self, maxsize: int, ttl: float):
        self.maxsize = maxsize
        self.ttl = ttl
        self._data: OrderedDict[str, tuple[float, T]] = OrderedDict()
        self._lock = Lock()

    def get(self, key: str) -> T | None:
        with self._lock:
            item = self._data.get(key)
            if item is None:
                return None
            if item[0] <= time.monotonic():
                self._data.pop(key, None)
                return None
            self._data.move_to_end(key)
            return item[1]

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._data[key] = (time.monotonic() + self.ttl, value)
            self._data.move_to_end(key)
            while len(self._data) > self.maxsize:
                self._data.popitem(last=False)


positive_cache: TTLCache[object] = TTLCache(maxsize=settings.public_import_cache_size, ttl=settings.public_import_cache_ttl_seconds)
negative_cache: TTLCache[object] = TTLCache(maxsize=settings.public_import_cache_size, ttl=60)
rate_limit_cache: TTLCache[object] = TTLCache(maxsize=settings.public_import_cache_size, ttl=15)
