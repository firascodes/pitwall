from datetime import datetime

import httpx

from pitwall.sources.openf1 import OpenF1Client, _query


def test_operator_filters_go_in_the_key() -> None:
    t = datetime.fromisoformat("2026-10-10T14:20:00+00:00")
    assert (
        _query({"session_key": 9, "date>=": t}) == "session_key=9&date>=2026-10-10T14:20:00%2B00:00"
    )


def test_404_means_no_results() -> None:
    transport = httpx.MockTransport(
        lambda r: httpx.Response(404, json={"detail": "No results found."})
    )
    client = OpenF1Client(
        httpx.Client(base_url="https://test", transport=transport), min_interval_s=0
    )
    assert client.get("laps", session_key=1) == []
