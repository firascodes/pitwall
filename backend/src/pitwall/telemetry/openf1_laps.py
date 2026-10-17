"""OpenF1 laps, tyre stints and race control messages -> source-agnostic Lap rows."""

import re
from bisect import bisect_right
from datetime import datetime
from typing import Any

from pitwall.telemetry.laps import LapProps, LapRow, lap_id

# "CAR 12 (ANT) TIME 1:32.818 DELETED - TRACK LIMITS AT TURN 2 LAP 8 21:42:03"
# "CAR 41 (LIN) LAP DELETED - TRACK LIMITS AT TURN 5 LAP 4 21:34:30 (PIT)"
DELETED_RE = re.compile(r"CAR (\d+) \(\w+\) (?:LAP|TIME \S+) DELETED - (.+?) LAP (\d+)\b")
# "CAR 44 (HAM) TIME 1:31.496 REINSTATED" style messages may follow a review
REINSTATED_RE = re.compile(r"CAR (\d+) \(\w+\) .*?\bLAP (\d+)\b.*?REINSTATED")


def _ms(seconds: float | None) -> int | None:
    return round(seconds * 1000) if seconds else None


def qualifying_phase_starts(race_control: list[dict[str, Any]]) -> list[tuple[datetime, str]]:
    """[(Q1 start, 'Q1'), (Q2 start, 'Q2'), (Q3 start, 'Q3')] from SESSION STARTED messages."""
    starts = [
        (datetime.fromisoformat(m["date"]), f"Q{m['qualifying_phase']}")
        for m in race_control
        if m["message"] == "SESSION STARTED" and m.get("qualifying_phase")
    ]
    return sorted(starts)


def part_for(lap_start: datetime | None, phases: list[tuple[datetime, str]]) -> str | None:
    """A lap belongs to the latest phase that started before it."""
    if lap_start is None or not phases:
        return None
    i = bisect_right([start for start, _ in phases], lap_start) - 1
    return phases[i][1] if i >= 0 else None


def deleted_laps(race_control: list[dict[str, Any]]) -> dict[tuple[int, int], str]:
    """(car number, lap number) -> reason, for laps deleted and not reinstated."""
    deleted: dict[tuple[int, int], str] = {}
    for m in sorted(race_control, key=lambda m: m["date"]):
        text = m["message"]
        if match := DELETED_RE.search(text):
            car, reason, lap = match.groups()
            deleted[(int(car), int(lap))] = reason.strip()
        elif match := REINSTATED_RE.search(text):
            deleted.pop((int(match.group(1)), int(match.group(2))), None)
    return deleted


def _tyres(stints: list[dict[str, Any]], car: int, lap: int) -> tuple[str | None, int | None, bool | None, int | None]:
    for s in stints:
        if s["driver_number"] == car and s["lap_start"] <= lap <= (s["lap_end"] or lap):
            age_at_start = s.get("tyre_age_at_start")
            age = age_at_start + (lap - s["lap_start"]) if age_at_start is not None else None
            fresh = age_at_start == 0 if age_at_start is not None else None
            return s.get("compound"), age, fresh, s.get("stint_number")
    return None, None, None, None


def lap_rows(
    session_id: str,
    laps: list[dict[str, Any]],
    stints: list[dict[str, Any]],
    race_control: list[dict[str, Any]],
    driver_by_number: dict[int, str],
) -> list[LapRow]:
    phases = qualifying_phase_starts(race_control) if session_id.endswith("-Q") else []
    deleted = deleted_laps(race_control)
    pit_out = {(lap["driver_number"], lap["lap_number"]) for lap in laps if lap.get("is_pit_out_lap")}

    rows = []
    best_so_far: dict[int, int] = {}
    for lap in sorted(laps, key=lambda lap: (lap["driver_number"], lap["lap_number"])):
        car, number = lap["driver_number"], lap["lap_number"]
        driver_id = driver_by_number.get(car)
        if driver_id is None:
            continue
        started = datetime.fromisoformat(lap["date_start"]) if lap.get("date_start") else None
        lap_ms = _ms(lap.get("lap_duration"))
        reason = deleted.get((car, number))
        personal_best = bool(lap_ms and not reason and lap_ms < best_so_far.get(car, 10**9))
        if personal_best:
            best_so_far[car] = lap_ms  # type: ignore[assignment]
        compound, tyre_age, fresh, tyre_stint = _tyres(stints, car, number)
        rows.append(LapRow(
            lap_id=lap_id(session_id, driver_id, number),
            result_id=f"{session_id}-{driver_id}",
            props=LapProps(
                lap_number=number,
                driver_number=car,
                started_at=started.isoformat() if started else None,
                lap_time_ms=lap_ms,
                s1_ms=_ms(lap.get("duration_sector_1")),
                s2_ms=_ms(lap.get("duration_sector_2")),
                s3_ms=_ms(lap.get("duration_sector_3")),
                compound=compound,
                tyre_age=tyre_age,
                fresh_tyre=fresh,
                tyre_stint=tyre_stint,
                part=part_for(started, phases),
                is_personal_best=personal_best,
                deleted=reason is not None,
                deleted_reason=reason,
                pit_in=(car, number + 1) in pit_out,  # the lap before a pit-out lap ends in the pits
                pit_out=bool(lap.get("is_pit_out_lap")),
                speed_trap_kph=lap.get("st_speed"),
            ),
        ))
    return rows
