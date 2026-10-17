"""Source-agnostic lap model: Lap rows for the graph and the hot set to pre-render."""

from pydantic import BaseModel


def lap_id(session_id: str, driver_id: str, lap_number: int) -> str:
    """'2026-17-Q' + 'hamilton' + 21 -> '2026-17-Q-hamilton-21' (shared key with Parquet)."""
    return f"{session_id}-{driver_id}-{lap_number:02d}"


def parse_lap_id(value: str) -> tuple[int, int, str, str, int]:
    """'2026-17-Q-hamilton-21' -> (2026, 17, 'Q', 'hamilton', 21). Driver ids have no '-'."""
    season, rnd, session_type, driver_id, lap_number = value.split("-")
    return int(season), int(rnd), session_type, driver_id, int(lap_number)


class LapProps(BaseModel):
    lap_number: int
    driver_number: int
    started_at: str | None  # ISO timestamp; the telemetry window starts here
    lap_time_ms: int | None
    s1_ms: int | None
    s2_ms: int | None
    s3_ms: int | None
    compound: str | None
    tyre_age: int | None
    fresh_tyre: bool | None
    tyre_stint: int | None  # tyre stint number; not the team Stint node
    part: str | None  # Q1/Q2/Q3 in qualifying
    is_personal_best: bool
    deleted: bool
    deleted_reason: str | None
    pit_in: bool
    pit_out: bool
    speed_trap_kph: float | None


class LapRow(BaseModel):
    lap_id: str
    result_id: str
    props: LapProps


def hot_set(rows: list[LapRow]) -> list[LapRow]:
    """Laps worth pre-rendering. Only push laps qualify: timed, with a start time, not deleted,
    and not an out-lap or in-lap (OpenF1 gives those a time too, garage time included).

    Qualifying: each driver's best lap per part, plus their last timed Q3 lap.
    Sprint and race: each driver's fastest lap.
    """
    timed = [
        r
        for r in rows
        if r.props.lap_time_ms
        and r.props.started_at  # no start time means no telemetry window
        and not r.props.deleted
        and not r.props.pit_in
        and not r.props.pit_out
    ]
    best: dict[tuple[str, str | None], LapRow] = {}
    last_q3: dict[str, LapRow] = {}
    for r in timed:
        key = (r.result_id, r.props.part)
        if key not in best or r.props.lap_time_ms < best[key].props.lap_time_ms:  # type: ignore[operator]
            best[key] = r
        if r.props.part == "Q3":
            current = last_q3.get(r.result_id)
            if current is None or r.props.lap_number > current.props.lap_number:
                last_q3[r.result_id] = r
    chosen = {r.lap_id: r for r in [*best.values(), *last_q3.values()]}
    return sorted(chosen.values(), key=lambda r: r.lap_id)
