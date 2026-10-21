import pytest

from pitwall.agent.tools.graph import graph_tools
from pitwall.graph.query import UnsafeCypher
from pitwall.graph.resolve import resolve_driver, resolve_race


@pytest.fixture(scope="module")
def tools(graph):
    return {t.name: t for t in graph_tools(graph, season=2026)}


def call(tool, **args):
    msg = tool.invoke({"name": tool.name, "args": args, "id": "t1", "type": "tool_call"})
    return msg.content, msg.artifact


def test_resolves_names_codes_and_latest(graph) -> None:
    assert resolve_driver(graph, "Lewis") == "hamilton"
    assert resolve_driver(graph, "VER") == "max_verstappen"
    assert resolve_race(graph, "singapore", 2026) == "2026-17"
    assert resolve_race(graph, "latest", 2026, "Q") == "2026-17"


def test_ambiguous_names_ask_the_user(graph) -> None:
    with pytest.raises(LookupError, match="ambiguous"):
        resolve_driver(graph, "an")


def test_session_results_formats_qualifying_times(tools) -> None:
    _, artifact = call(tools["session_results"], race="Singapore", session="Q")
    assert artifact["kind"] == "rows"
    pole = artifact["data"][0]
    assert pole["pos"] == 1 and pole["q3"].startswith("1:")
    assert "grid" not in pole  # empty columns are dropped


def test_teammate_battle_reads_from_the_drivers_side(tools) -> None:
    _, artifact = call(tools["teammate_battle"], driver_name="Lawson")
    assert artifact["kind"] == "h2h"
    assert {r["driver"] for r in artifact["data"]} == {"Liam Lawson"}
    assert len(artifact["data"]) >= 2  # he moved team mid-season


def test_deleted_laps_have_a_reason(tools) -> None:
    _, artifact = call(tools["session_laps"], race="17", session="Q", only="deleted")
    assert len(artifact["data"]) == 11
    assert all(r["deleted_reason"] for r in artifact["data"])


def test_run_cypher_refuses_writes(tools) -> None:
    with pytest.raises(UnsafeCypher):
        call(tools["run_cypher"], query="MATCH (n) DETACH DELETE n")


def test_tools_report_the_cypher_they_ran(tools) -> None:
    _, artifact = call(tools["session_results"], race="Singapore", session="Q")
    queries = artifact["queries"]
    assert [q["params"].get("race_id") for q in queries] == [None, "2026-17"]
    assert "MATCH (r:Race" in queries[0]["cypher"] and queries[1]["rows"] == 22
