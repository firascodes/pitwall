from pathlib import Path

import pytest

from pitwall.agent.tools.laps import lap_tools
from pitwall.config import get_settings
from pitwall.telemetry.store import TelemetryStore


def _no_download(lap: str):
    raise AssertionError(f"{lap} should come from the Parquet cache")


@pytest.fixture(scope="module")
def tools(graph):
    s = get_settings()
    if not (s.telemetry_dir / "2026/17/Q/hamilton/21.parquet").exists():
        pytest.skip("Singapore telemetry is not ingested")
    store = TelemetryStore(s.telemetry_dir, _no_download)
    return {t.name: t for t in lap_tools(graph, store, Path(s.circuits_dir), 2026)}


async def call(tool, **args):
    msg = await tool.ainvoke({"name": tool.name, "args": args, "id": "t1", "type": "tool_call"})
    return msg.artifact


@pytest.mark.parametrize(
    ("which", "lap_id", "time"),
    [
        ("fastest", "2026-17-Q-hamilton-21", "1:31.496"),
        (
            "last_q3",
            "2026-17-Q-hamilton-24",
            "1:31.648",
        ),  # his second Q3 run, not the cool-down lap
    ],
)
async def test_find_lap_picks_push_laps(tools, which, lap_id, time) -> None:
    lap = await call(
        tools["find_lap"], driver_name="Hamilton", race="Singapore", session="Q", which=which
    )
    assert lap["kind"] == "lap"
    assert (lap["data"]["lap_id"], lap["data"]["time"]) == (lap_id, time)


async def test_compare_laps_uses_official_times_and_adds_up_by_corner(tools) -> None:
    result = await call(
        tools["compare_laps"], lap_a="2026-17-Q-hamilton-21", lap_b="2026-17-Q-leclerc-24"
    )
    data = result["data"]
    assert result["kind"] == "lap_compare"
    assert data["a"]["time"] == "1:31.496"
    assert [c["corner"] for c in data["corners"]][:3] == ["T1", "T2", "T3"]
    corner_sum = sum(c["a_gain_s"] for c in data["corners"])
    assert corner_sum == pytest.approx(data["gap"]["b_behind_a_s"][-1], abs=0.02)


async def test_compare_laps_rejects_laps_from_different_weekends(tools) -> None:
    with pytest.raises(ValueError, match="same race weekend"):
        await call(
            tools["compare_laps"], lap_a="2026-17-Q-hamilton-21", lap_b="2026-16-Q-leclerc-10"
        )
