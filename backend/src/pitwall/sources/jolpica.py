"""Client for the Jolpica-F1 API (the Ergast-compatible successor)."""

import logging
import time
from typing import Any

import httpx

BASE_URL = "https://api.jolpi.ca/ergast/f1"
PAGE_SIZE = 100  # the API maximum
MIN_INTERVAL_S = 0.3  # stay under the 4 requests/second burst limit
MAX_ATTEMPTS = 5

# Which key holds the per-driver rows for each endpoint
RESULT_KEYS = {
    "results": "Results",
    "qualifying": "QualifyingResults",
    "sprint": "SprintResults",
}

log = logging.getLogger(__name__)


class JolpicaClient:
    def __init__(self, http: httpx.Client | None = None) -> None:
        self._http = http or httpx.Client(base_url=BASE_URL, timeout=30)
        self._last_request_at = 0.0

    def fetch_races(self, season: int, endpoint: str) -> list[dict[str, Any]]:
        """Every race for an endpoint ("races", "results", "qualifying", "sprint").

        Jolpica paginates by result row, not by race, so one race can be split across
        two pages. Pages are merged by round number.
        """
        results_key = RESULT_KEYS.get(endpoint)
        by_round: dict[int, dict[str, Any]] = {}
        offset = 0
        while True:
            data = self._get(f"/{season}/{endpoint}/", {"limit": PAGE_SIZE, "offset": offset})
            for race in data["RaceTable"]["Races"]:
                rnd = int(race["round"])
                if rnd in by_round and results_key:
                    by_round[rnd][results_key].extend(race[results_key])
                else:
                    by_round[rnd] = race
            offset += PAGE_SIZE
            if offset >= int(data["total"]):
                break
        return [by_round[rnd] for rnd in sorted(by_round)]

    def _get(self, path: str, params: dict[str, int]) -> dict[str, Any]:
        for attempt in range(MAX_ATTEMPTS):
            self._throttle()
            response = self._http.get(path, params=params)
            if response.status_code == 429 or response.status_code >= 500:
                backoff_s = 2**attempt
                log.warning(
                    "Jolpica %s on %s, retrying in %ss", response.status_code, path, backoff_s
                )
                time.sleep(backoff_s)
                continue
            response.raise_for_status()
            return response.json()["MRData"]
        raise RuntimeError(f"Jolpica request failed after {MAX_ATTEMPTS} attempts: {path}")

    def _throttle(self) -> None:
        wait_s = MIN_INTERVAL_S - (time.monotonic() - self._last_request_at)
        if wait_s > 0:
            time.sleep(wait_s)
        self._last_request_at = time.monotonic()
