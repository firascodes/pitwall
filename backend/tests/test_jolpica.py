import httpx

from pitwall.sources import jolpica
from pitwall.sources.jolpica import JolpicaClient


def _race(rnd: int, drivers: list[str]) -> dict:
    return {"season": "2026", "round": str(rnd), "Results": [{"driver": d} for d in drivers]}


def test_race_split_across_pages_is_merged(monkeypatch) -> None:
    monkeypatch.setattr(jolpica, "PAGE_SIZE", 3)
    monkeypatch.setattr(jolpica, "MIN_INTERVAL_S", 0)
    pages = {
        0: [_race(1, ["a", "b"]), _race(2, ["a"])],  # round 2 starts on page 1...
        3: [_race(2, ["b"])],  # ...and ends on page 2
    }

    def handler(request: httpx.Request) -> httpx.Response:
        offset = int(request.url.params["offset"])
        body = {"MRData": {"total": "4", "RaceTable": {"Races": pages[offset]}}}
        return httpx.Response(200, json=body)

    client = JolpicaClient(
        httpx.Client(base_url="https://test", transport=httpx.MockTransport(handler))
    )
    races = client.fetch_races(2026, "results")

    assert [r["round"] for r in races] == ["1", "2"]
    assert [row["driver"] for row in races[1]["Results"]] == ["a", "b"]
