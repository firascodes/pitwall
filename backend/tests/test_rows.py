import pytest

from pitwall.ingest.rows import parse_lap_time_ms, result_rows


@pytest.mark.parametrize(
    ("value", "expected"),
    [("1:19.507", 79507), ("59.123", 59123), ("", None), (None, None)],
)
def test_parse_lap_time_ms(value: str | None, expected: int | None) -> None:
    assert parse_lap_time_ms(value) == expected


def _entry(driver_id: str, position: str, position_text: str) -> dict:
    return {
        "position": position,
        "positionText": position_text,
        "points": "0",
        "Driver": {"driverId": driver_id, "givenName": "A", "familyName": "B"},
        "Constructor": {"constructorId": "ferrari", "name": "Ferrari"},
    }


def test_race_result_ids_and_classification() -> None:
    race = {
        "season": "2026",
        "round": "7",
        "Results": [_entry("hamilton", "3", "3"), _entry("leclerc", "18", "R")],
    }

    rows = result_rows("results", [race], "Results")

    assert [r.result_id for r in rows] == ["2026-07-R-hamilton", "2026-07-R-leclerc"]
    assert [r.props.classified for r in rows] == [True, False]  # "R" = retired
