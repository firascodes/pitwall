"""Load every lap into the graph and pre-render the hot set of lap telemetry (OpenF1)."""

import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from neo4j import Driver

from pitwall.graph.schema import apply_schema
from pitwall.ingest.load import write_rows
from pitwall.sources.openf1 import SESSION_NAMES, OpenF1Client
from pitwall.telemetry.laps import LapRow, hot_set
from pitwall.telemetry.openf1_laps import lap_rows
from pitwall.telemetry.openf1_telemetry import build_lap_frame, lap_window, slice_window
from pitwall.telemetry.resample import resample_lap
from pitwall.telemetry.store import lap_path, write_lap

log = logging.getLogger(__name__)

SESSIONS_QUERY = """
MATCH (r:Race)-[:HAS_SESSION]->(s:Session)
WHERE r.season = $season AND ($round IS NULL OR r.round = $round)
  AND EXISTS { (s)<-[:IN_SESSION]-(:Result) }
RETURN s.session_id AS session_id, s.type AS type, s.starts_at AS starts_at
ORDER BY r.round, s.type
"""

CODES_QUERY = """
MATCH (d:Driver)-[:ACHIEVED]->(:Result)-[:IN_SESSION]->(:Session {session_id: $session_id})
RETURN d.code AS code, d.driver_id AS driver_id
"""

LAPS_CYPHER = """
UNWIND $rows AS row
MATCH (res:Result {result_id: row.result_id})
MERGE (l:Lap {lap_id: row.lap_id})
  SET l += row.props, l.started_at = datetime(row.props.started_at)
MERGE (res)-[:HAS_LAP]->(l)
"""

# Same-type sessions are a week apart, so the nearest one within a day is the match.
# (Start times can disagree: Miami 2026 is 17:00 UTC in OpenF1 but 20:00 in Jolpica.)
MATCH_WINDOW = timedelta(hours=24)


def match_openf1_session(
    sessions: list[dict[str, Any]], session_type: str, starts_at: datetime
) -> int:
    """Entity resolution across sources: same session type, nearest start time."""
    name = SESSION_NAMES[session_type]
    candidates = [
        (abs(datetime.fromisoformat(s["date_start"]) - starts_at), s["session_key"])
        for s in sessions
        if s["session_name"] == name
    ]
    gap, key = min(candidates, default=(MATCH_WINDOW, None))
    if key is None or gap >= MATCH_WINDOW:
        raise LookupError(f"no OpenF1 {name} session near {starts_at}")
    return key


def _render_hot_laps(
    client: OpenF1Client, root: Path, session_key: int, hot: list[LapRow]
) -> tuple[int, int]:
    """One car_data + one location request per driver, covering all their hot laps."""
    written = failed = 0
    by_car: dict[int, list[LapRow]] = defaultdict(list)
    for row in hot:
        if not lap_path(root, row.lap_id).exists():
            by_car[row.props.driver_number].append(row)
    for car, rows in by_car.items():
        windows = {r.lap_id: lap_window(r.props.started_at, r.props.lap_time_ms) for r in rows}  # type: ignore[arg-type]
        start = min(w[0] for w in windows.values())
        end = max(w[1] for w in windows.values())
        car_data = client.car_data(session_key, car, start, end)
        location = client.location(session_key, car, start, end)
        for lap, (lap_start, lap_end) in windows.items():
            try:
                frame = build_lap_frame(
                    slice_window(car_data, lap_start, lap_end),
                    slice_window(location, lap_start, lap_end),
                    lap_start,
                )
                write_lap(root, lap, resample_lap(frame, lap))
                written += 1
            except Exception:  # one bad lap must not stop the session
                log.exception("telemetry failed for %s", lap)
                failed += 1
    return written, failed


def ingest_session_laps(
    driver: Driver,
    client: OpenF1Client,
    openf1_sessions: list[dict[str, Any]],
    root: Path,
    session_id: str,
    session_type: str,
    starts_at: datetime,
) -> dict[str, Any]:
    started, requests_before = time.monotonic(), client.requests

    key = match_openf1_session(openf1_sessions, session_type, starts_at)
    driver.execute_query(
        "MATCH (s:Session {session_id: $sid}) SET s.openf1_session_key = $key",
        sid=session_id,
        key=key,
    )

    records, _, _ = driver.execute_query(CODES_QUERY, session_id=session_id)
    code_to_id = {r["code"]: r["driver_id"] for r in records}
    by_number = {
        d["driver_number"]: code_to_id[d["name_acronym"]]
        for d in client.get("drivers", session_key=key)
        if d.get("name_acronym") in code_to_id
    }

    rows = lap_rows(
        session_id,
        client.get("laps", session_key=key),
        client.get("stints", session_key=key),
        client.get("race_control", session_key=key),
        by_number,
    )
    write_rows(driver, LAPS_CYPHER, rows)

    hot = hot_set(rows)
    written, failed = _render_hot_laps(client, root, key, hot)
    parquet_kb = (
        sum(
            lap_path(root, r.lap_id).stat().st_size
            for r in hot
            if lap_path(root, r.lap_id).exists()
        )
        // 1024
    )
    return {
        "session_id": session_id,
        "openf1_key": key,
        "drivers_matched": len(by_number),
        "laps": len(rows),
        "deleted": sum(r.props.deleted for r in rows),
        "hot_laps": len(hot),
        "written": written,
        "failed": failed,
        "requests": client.requests - requests_before,
        "total_s": round(time.monotonic() - started, 1),
        "parquet_kb": parquet_kb,
    }


def run_laps_ingest(driver: Driver, root: Path, season: int, rnd: int | None = None) -> list[dict]:
    apply_schema(driver)
    client = OpenF1Client()
    openf1_sessions = client.get("sessions", year=season)
    records, _, _ = driver.execute_query(SESSIONS_QUERY, season=season, round=rnd)
    metrics = []
    for rec in records:
        log.info("laps for %s", rec["session_id"])
        try:
            m = ingest_session_laps(
                driver,
                client,
                openf1_sessions,
                root,
                rec["session_id"],
                rec["type"],
                rec["starts_at"].to_native(),
            )
        except Exception:  # keep going; the summary shows what failed
            log.exception("session %s failed", rec["session_id"])
            m = {"session_id": rec["session_id"], "error": True}
        log.info("%s", m)
        metrics.append(m)
    out = root.parent / "ingest_metrics" / f"laps-{season}{'' if rnd is None else f'-r{rnd}'}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(metrics, indent=2))
    return metrics
