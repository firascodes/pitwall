"""Client for the OpenF1 API (historical data, free tier, non-commercial use).

Free tier limits: 3 requests/second and 30 requests/minute. The minute limit is the
binding one, so requests are spaced 2.1 s apart.
"""

import logging
import time
from datetime import datetime
from typing import Any
from urllib.parse import quote

import httpx

BASE_URL = "https://api.openf1.org/v1"
MIN_INTERVAL_S = 2.1
MAX_ATTEMPTS = 5

SESSION_NAMES = {"Q": "Qualifying", "S": "Sprint", "R": "Race"}

log = logging.getLogger(__name__)


def _query(filters: dict[str, Any]) -> str:
    """{'session_key': 9, 'date>=': t} -> 'session_key=9&date>=...'.

    OpenF1 puts comparison operators in the key, so httpx `params` can't express them.
    """
    parts = []
    for key, value in filters.items():
        text = value.isoformat() if isinstance(value, datetime) else str(value)
        separator = "" if key[-1] in "<>=" else "="
        parts.append(f"{key}{separator}{quote(text, safe=':')}")
    return "&".join(parts)


class OpenF1Client:
    def __init__(self, http: httpx.Client | None = None, min_interval_s: float = MIN_INTERVAL_S):
        self._http = http or httpx.Client(base_url=BASE_URL, timeout=60)
        self._min_interval_s = min_interval_s
        self._last_request_at = 0.0
        self.requests = 0

    def get(self, endpoint: str, **filters: Any) -> list[dict[str, Any]]:
        url = f"/{endpoint}?{_query(filters)}"
        for attempt in range(MAX_ATTEMPTS):
            self._throttle()
            response = self._http.get(url)
            self.requests += 1
            if response.status_code == 404:
                return []  # OpenF1 answers "No results found." with a 404
            if response.status_code == 429 or response.status_code >= 500:
                backoff_s = 5 * 2**attempt
                log.warning(
                    "OpenF1 %s on %s, retrying in %ss", response.status_code, url, backoff_s
                )
                time.sleep(backoff_s)
                continue
            response.raise_for_status()
            return response.json()
        raise RuntimeError(f"OpenF1 request failed after {MAX_ATTEMPTS} attempts: {url}")

    def car_data(
        self, session_key: int, driver_number: int, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        return self.get(
            "car_data",
            session_key=session_key,
            driver_number=driver_number,
            **{"date>=": start, "date<=": end},
        )

    def location(
        self, session_key: int, driver_number: int, start: datetime, end: datetime
    ) -> list[dict[str, Any]]:
        return self.get(
            "location",
            session_key=session_key,
            driver_number=driver_number,
            **{"date>=": start, "date<=": end},
        )

    def _throttle(self) -> None:
        wait_s = self._min_interval_s - (time.monotonic() - self._last_request_at)
        if wait_s > 0:
            time.sleep(wait_s)
        self._last_request_at = time.monotonic()
