from pitwall.agent.answer import (
    ChipsDraft,
    ComponentDraft,
    Draft,
    Source,
    TextDraft,
    catalog,
    hydrate,
)

COMPARE = {
    "a": {"lap_id": "2026-17-Q-hamilton-21", "driver": "Lewis Hamilton", "time": "1:31.496"},
    "b": {"lap_id": "2026-17-Q-leclerc-24", "driver": "Charles Leclerc", "time": "1:31.512"},
    "corners": [{"corner": "T1", "a_gain_s": 0.078}],
    "gap": {"distance_m": [0.0, 25.0], "b_behind_a_s": [0.0, 0.01]},
}
SOURCES = {
    "r1": Source("r1", "compare_laps", "lap_compare", COMPARE, "{}"),
    "r2": Source("r2", "standings", "rows", [], "[]"),
}


def component(name: str, source: str) -> ComponentDraft:
    return ComponentDraft(type="component", component=name, source=source, title=name)


def test_components_are_filled_from_the_referenced_tool_result() -> None:
    draft = Draft(
        blocks=[
            TextDraft(type="text", text="Hamilton was 0.016 s faster [r1]."),
            component("lap_replay", "r1"),
            component("delta_chart", "r1"),
            ChipsDraft(type="chips", options=["Q2 laps?", "Race pace?", "Tyres?", "Too many"]),
        ]
    )
    blocks = hydrate(draft, SOURCES)
    assert [b["type"] for b in blocks] == ["text", "lap_replay", "delta_chart", "chips"]
    assert blocks[1]["data"] == {
        "laps": [COMPARE["a"]["lap_id"], COMPARE["b"]["lap_id"]],
        "ghost": True,
    }
    assert blocks[2]["data"]["b_behind_a_s"] == [0.0, 0.01]
    assert len(blocks[3]["options"]) == 3


def test_invalid_components_are_dropped() -> None:
    draft = Draft(
        blocks=[
            component("h2h_card", "r1"),  # wrong kind for a lap comparison
            component("results_table", "r2"),  # empty result
            component("corner_table", "r9"),  # no such source
            *[component("corner_table", "r1") for _ in range(5)],  # over the limit of 4
        ]
    )
    assert [b["type"] for b in hydrate(draft, SOURCES)] == ["corner_table"] * 4


def test_catalog_lists_what_each_source_can_fill() -> None:
    assert "[r1] compare_laps -> can fill: corner_table, delta_chart, lap_replay" in catalog(
        SOURCES
    )
