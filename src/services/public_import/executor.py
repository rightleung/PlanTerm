from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import Callable, TypeVar

from src.config import settings
from .errors import ProviderTimeoutError


R = TypeVar("R")
_pool = ThreadPoolExecutor(max_workers=settings.public_import_workers, thread_name_prefix="planterm-public-import")
_semaphore = asyncio.Semaphore(settings.public_import_workers)


async def bounded_call(fn: Callable[[], R], timeout: float = 8.0) -> R:
    acquired = False
    try:
        await _semaphore.acquire()
        acquired = True
        loop = asyncio.get_running_loop()
        future = loop.run_in_executor(_pool, partial(fn))
        try:
            return await asyncio.wait_for(asyncio.shield(future), timeout=timeout)
        except asyncio.TimeoutError:
            # A thread cannot be force-cancelled. Keep the semaphore slot
            # occupied until the underlying provider call really completes.
            future.add_done_callback(lambda _completed: _semaphore.release())
            acquired = False
            raise
        except asyncio.CancelledError:
            # The total request deadline cancels this coroutine, but it cannot
            # cancel a blocking provider running in the thread pool. Keep the
            # slot occupied until that provider call really completes.
            future.add_done_callback(lambda _completed: _semaphore.release())
            acquired = False
            raise
    except asyncio.TimeoutError as exc:
        raise ProviderTimeoutError(details={"retryable": True}) from exc
    finally:
        if acquired:
            _semaphore.release()
