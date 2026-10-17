"""Cross-process locks, so two workers never download the same session at once."""

import hashlib
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol

import psycopg


class SessionLock(Protocol):
    def __call__(self, key: str) -> AbstractAsyncContextManager[None]: ...


def lock_id(key: str) -> int:
    """Postgres advisory locks take a 64-bit integer: hash the string key into one."""
    return int.from_bytes(hashlib.sha256(key.encode()).digest()[:8], "big", signed=True)


def postgres_lock(dsn: str) -> SessionLock:
    @asynccontextmanager
    async def lock(key: str) -> AsyncIterator[None]:
        # Transaction-level advisory lock: released on commit/rollback, and also when the
        # connection drops, so a crashed worker can never leave a lock stuck.
        async with await psycopg.AsyncConnection.connect(dsn) as conn, conn.transaction():
            await conn.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id(key),))
            yield

    return lock


@asynccontextmanager
async def no_lock(key: str) -> AsyncIterator[None]:
    """For tests and single-process scripts."""
    yield
