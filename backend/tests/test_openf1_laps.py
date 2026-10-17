from pitwall.telemetry.openf1_laps import deleted_laps, lap_rows, part_for, qualifying_phase_starts

RACE_CONTROL = [
    {"date": "2026-10-10T13:30:00+00:00", "message": "SESSION STARTED", "qualifying_phase": 1},
    {
        "date": "2026-10-10T13:43:35+00:00",
        "message": "CAR 12 (ANT) TIME 1:32.818 DELETED - TRACK LIMITS AT TURN 2 LAP 8 21:42:03",
        "qualifying_phase": None,
    },
    {
        "date": "2026-10-10T13:36:22+00:00",
        "message": "CAR 41 (LIN) LAP DELETED - TRACK LIMITS AT TURN 5 LAP 4 21:34:30 (PIT)",
        "qualifying_phase": None,
    },
    {"date": "2026-10-10T13:55:00+00:00", "message": "SESSION STARTED", "qualifying_phase": 2},
    {"date": "2026-10-10T14:17:00+00:00", "message": "SESSION STARTED", "qualifying_phase": 3},
]


def test_deleted_laps_parse_both_message_formats() -> None:
    assert deleted_laps(RACE_CONTROL) == {
        (12, 8): "TRACK LIMITS AT TURN 2",
        (41, 4): "TRACK LIMITS AT TURN 5",
    }


def test_reinstated_lap_is_no_longer_deleted() -> None:
    messages = [
        *RACE_CONTROL,
        {
            "date": "2026-10-10T14:40:00+00:00",
            "message": "CAR 12 (ANT) LAP 8 TIME 1:32.818 REINSTATED",
            "qualifying_phase": None,
        },
    ]
    assert (12, 8) not in deleted_laps(messages)


def test_lap_part_is_the_latest_phase_started_before_it() -> None:
    phases = qualifying_phase_starts(RACE_CONTROL)
    from datetime import datetime

    assert part_for(datetime.fromisoformat("2026-10-10T13:50:00+00:00"), phases) == "Q1"
    assert part_for(datetime.fromisoformat("2026-10-10T14:20:00+00:00"), phases) == "Q3"


def _lap(car: int, number: int, start: str, duration: float | None, pit_out: bool = False) -> dict:
    return {
        "driver_number": car,
        "lap_number": number,
        "date_start": start,
        "lap_duration": duration,
        "is_pit_out_lap": pit_out,
        "duration_sector_1": None,
        "duration_sector_2": None,
        "duration_sector_3": None,
        "st_speed": 300,
    }


def test_lap_rows_tyres_pits_parts_and_personal_bests() -> None:
    laps = [
        _lap(44, 1, "2026-10-10T13:31:00+00:00", None, pit_out=True),
        _lap(44, 2, "2026-10-10T13:33:00+00:00", 93.0),
        _lap(44, 3, "2026-10-10T13:35:00+00:00", 94.0),
        _lap(44, 4, "2026-10-10T14:18:00+00:00", 91.5, pit_out=True),
    ]
    stints = [
        {
            "driver_number": 44,
            "lap_start": 1,
            "lap_end": 3,
            "compound": "SOFT",
            "tyre_age_at_start": 0,
            "stint_number": 1,
        }
    ]

    rows = lap_rows("2026-17-Q", laps, stints, RACE_CONTROL, {44: "hamilton"})
    by_lap = {r.props.lap_number: r.props for r in rows}

    assert rows[0].lap_id == "2026-17-Q-hamilton-01"
    assert (by_lap[3].compound, by_lap[3].tyre_age, by_lap[3].fresh_tyre) == ("SOFT", 2, True)
    assert by_lap[3].pit_in  # lap 4 is a pit-out lap, so lap 3 ended in the pits
    assert [by_lap[n].part for n in (2, 4)] == ["Q1", "Q3"]
    assert [by_lap[n].is_personal_best for n in (2, 3, 4)] == [True, False, True]
