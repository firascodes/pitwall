"""Guards for the public demo: per-IP rate limits and a daily LLM spend cap (one process)."""

import time
from collections import defaultdict, deque
from datetime import UTC, datetime

import psycopg
from fastapi import Request

LEDGER = """
CREATE TABLE IF NOT EXISTS llm_spend (day date PRIMARY KEY, usd double precision NOT NULL)
"""
ADD = """
INSERT INTO llm_spend (day, usd) VALUES (%s, %s)
ON CONFLICT (day) DO UPDATE SET usd = llm_spend.usd + EXCLUDED.usd
"""


class RateLimiter:
    """Sliding window: at most `limit` requests per `window_s` seconds for each key."""

    def __init__(self, limit: int, window_s: float = 60.0) -> None:
        self.limit, self.window_s = limit, window_s
        self.hits: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, key: str) -> bool:
        now, hits = time.monotonic(), self.hits[key]
        while hits and now - hits[0] > self.window_s:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True


class DailyBudget:
    """LLM spend for the current UTC day; it resets at midnight.

    With a database, the spend survives restarts (free hosts sleep and restart often).
    """

    def __init__(self, cap_usd: float, dsn: str | None = None) -> None:
        self.cap_usd, self.dsn = cap_usd, dsn
        self.day, self.spent_usd = self._today(), 0.0

    async def load(self) -> None:
        if self.dsn is None:
            return
        async with await psycopg.AsyncConnection.connect(self.dsn, autocommit=True) as conn:
            await conn.execute(LEDGER)
            row = await (
                await conn.execute("SELECT usd FROM llm_spend WHERE day = %s", (self.day,))
            ).fetchone()
        self.spent_usd = row[0] if row else 0.0

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).date().isoformat()

    def _roll(self) -> None:
        if (today := self._today()) != self.day:
            self.day, self.spent_usd = today, 0.0

    def exhausted(self) -> bool:
        self._roll()
        return self.spent_usd >= self.cap_usd

    async def add(self, usd: float) -> None:
        self._roll()
        self.spent_usd += usd
        if self.dsn is not None and usd > 0:
            async with await psycopg.AsyncConnection.connect(self.dsn, autocommit=True) as conn:
                await conn.execute(ADD, (self.day, usd))

    def report(self) -> dict[str, float | str]:
        self._roll()
        return {"day": self.day, "spent_usd": round(self.spent_usd, 6), "cap_usd": self.cap_usd}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
