from pitwall.telemetry.laps import LapProps, LapRow, hot_set, lap_id, parse_lap_id


def _row(
    driver: str,
    number: int,
    ms: int | None,
    part: str | None = None,
    deleted: bool = False,
    pit_in: bool = False,
    pit_out: bool = False,
) -> LapRow:
    session = "2026-17-Q" if part else "2026-17-R"
    props = LapProps(
        lap_number=number,
        driver_number=1,
        started_at=None,
        lap_time_ms=ms,
        s1_ms=None,
        s2_ms=None,
        s3_ms=None,
        compound=None,
        tyre_age=None,
        fresh_tyre=None,
        tyre_stint=None,
        part=part,
        is_personal_best=False,
        deleted=deleted,
        deleted_reason=None,
        pit_in=pit_in,
        pit_out=pit_out,
        speed_trap_kph=None,
    )
    return LapRow(
        lap_id=lap_id(session, driver, number), result_id=f"{session}-{driver}", props=props
    )


def test_lap_id_round_trip() -> None:
    assert parse_lap_id("2026-17-Q-max_verstappen-07") == (2026, 17, "Q", "max_verstappen", 7)


def test_qualifying_hot_set_is_best_per_part_plus_last_q3_and_skips_deleted() -> None:
    rows = [
        _row("hamilton", 3, 93_000, "Q1"),
        _row("hamilton", 5, 92_000, "Q1"),
        _row("hamilton", 20, 91_400, "Q3", deleted=True),  # fastest, but track limits
        _row("hamilton", 21, 91_496, "Q3"),
        _row("hamilton", 23, 91_600, "Q3"),  # slower, but his last Q3 lap
        _row("hamilton", 24, None, "Q3"),  # in-lap, no time
    ]
    assert [r.props.lap_number for r in hot_set(rows)] == [5, 21, 23]


def test_race_hot_set_is_fastest_lap_per_driver() -> None:
    rows = [_row("leclerc", 10, 97_000), _row("leclerc", 40, 96_100), _row("hamilton", 12, 96_900)]
    assert {r.lap_id for r in hot_set(rows)} == {"2026-17-R-leclerc-40", "2026-17-R-hamilton-12"}


def test_out_laps_and_in_laps_never_count_as_last_q3_lap() -> None:
    rows = [
        _row("hamilton", 20, 552_871, "Q3", pit_out=True),  # out-lap: garage time included
        _row("hamilton", 21, 91_496, "Q3"),
        _row("hamilton", 22, 108_956, "Q3", pit_in=True),  # cool-down lap into the pits
    ]
    assert [r.props.lap_number for r in hot_set(rows)] == [21]
