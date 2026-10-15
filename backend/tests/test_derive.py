import pytest

from pitwall.ingest.derive import derive_stints, derive_teammates


def _result(driver: str, team: str, rnd: int, kind: str = "Q", position: int = 1, **times) -> dict:
    return {
        "driver_id": driver,
        "team_id": team,
        "round": rnd,
        "session_id": f"2025-{rnd:02d}-{kind}",
        "session_type": kind,
        "result_id": f"2025-{rnd:02d}-{kind}-{driver}",
        "position": position,
        "classified": True,
        "q1_ms": times.get("q1"),
        "q2_ms": times.get("q2"),
        "q3_ms": times.get("q3"),
    }


def test_mid_season_swap_makes_two_stints() -> None:
    results = [
        _result("lawson", "red_bull", 1),
        _result("lawson", "red_bull", 2),
        _result("lawson", "rb", 3),
        _result("lawson", "rb", 4),
    ]

    stints = derive_stints(2025, results)

    assert [(s["team_id"], s["from_round"], s["to_round"]) for s in stints] == [
        ("red_bull", 1, 2),
        ("rb", 3, 4),
    ]


def test_teammate_pair_is_ordered_and_gaps_are_opposite() -> None:
    results = [
        # verstappen beats tsunoda in Q3; driver ids sort tsunoda < verstappen
        _result("verstappen", "red_bull", 3, position=1, q3=80_000),
        _result("tsunoda", "red_bull", 3, position=9, q3=80_400),
    ]

    pairs, gaps = derive_teammates(2025, results)

    assert len(pairs) == 1
    pair = pairs[0]
    assert (pair.a, pair.b) == ("tsunoda", "verstappen")
    assert pair.quali_h2h == [0, 1]
    assert gaps["2025-03-Q-tsunoda"] == pytest.approx(-gaps["2025-03-Q-verstappen"])
    assert gaps["2025-03-Q-tsunoda"] > 0  # tsunoda was slower


def test_race_h2h_ignores_unclassified_cars() -> None:
    a = _result("hamilton", "ferrari", 5, kind="R", position=4)
    b = _result("leclerc", "ferrari", 5, kind="R", position=19)
    b["classified"] = False

    pairs, _ = derive_teammates(2026, [a, b])

    assert pairs[0].race_h2h == [0, 0]
