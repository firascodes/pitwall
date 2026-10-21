"""Guards for the public demo: per-IP rate limits and a daily LLM spend cap (one process)."""

import time
from collections import defaultdict, deque
from datetime import UTC, datetime

from fastapi import Request


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
    """LLM spend for the current UTC day; it resets at midnight."""

    def __init__(self, cap_usd: float) -> None:
        self.cap_usd = cap_usd
        self.day, self.spent_usd = self._today(), 0.0

    @staticmethod
    def _today() -> str:
        return datetime.now(UTC).date().isoformat()

    def _roll(self) -> None:
        if (today := self._today()) != self.day:
            self.day, self.spent_usd = today, 0.0

    def exhausted(self) -> bool:
        self._roll()
        return self.spent_usd >= self.cap_usd

    def add(self, usd: float) -> None:
        self._roll()
        self.spent_usd += usd

    def report(self) -> dict[str, float | str]:
        self._roll()
        return {"day": self.day, "spent_usd": round(self.spent_usd, 6), "cap_usd": self.cap_usd}


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
