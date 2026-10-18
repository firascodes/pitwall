"""Telemetry tools: find a lap, then compare two laps corner by corner."""

import asyncio
from pathlib import Path
from typing import Annotated, Literal

from langchain_core.tools import BaseTool, tool
from neo4j import Driver

from pitwall.agent.tools.common import SessionType, lap_time, output
from pitwall.graph.query import read_rows
from pitwall.graph.resolve import resolve_driver, resolve_race
from pitwall.telemetry.compare import as_rows, corner_gains, gap
from pitwall.telemetry.corners import corner_distances, load_corners
from pitwall.telemetry.laps import parse_lap_id
from pitwall.telemetry.store import TelemetryStore

GAP_EVERY = 5  # one chart point per 25 m

FIND_LAP = """
MATCH (:Race {race_id: $race_id})-[:HAS_SESSION]->(:Session {type: $type})
      <-[:IN_SESSION]-(res:Result),
      (d:Driver {driver_id: $driver_id})-[:ACHIEVED]->(res)-[:HAS_LAP]->(l:Lap)
WHERE CASE
  WHEN $lap_number IS NOT NULL THEN l.lap_number = $lap_number
  ELSE l.lap_time_ms IS NOT NULL AND NOT l.deleted AND NOT l.pit_in AND NOT l.pit_out
       AND ($which <> 'last_q3' OR l.part = 'Q3')
END
RETURN l.lap_id AS lap_id, d.name AS driver, l.lap_number AS lap, l.lap_time_ms AS ms,
       l.part AS part, l.compound AS compound, l.tyre_age AS tyre_age
ORDER BY CASE $which WHEN 'last_q3' THEN -l.lap_number ELSE l.lap_time_ms END
LIMIT 1
"""

LAP_FACTS = """
MATCH (d:Driver)-[:ACHIEVED]->(res:Result)-[:HAS_LAP]->(l:Lap {lap_id: $lap_id}),
      (res)-[:IN_SESSION]->(s:Session)
RETURN d.name AS driver, l.lap_time_ms AS ms, s.openf1_session_key AS session_key
"""


def lap_tools(
    driver: Driver, store: TelemetryStore, circuits_dir: Path, season: int
) -> list[BaseTool]:
    def facts(lap_id: str) -> dict:
        rows = read_rows(driver, LAP_FACTS, lap_id=lap_id)
        if not rows:
            raise LookupError(f"unknown lap '{lap_id}': call find_lap first to get a lap_id")
        return rows[0]

    @tool(response_format="content_and_artifact")
    def find_lap(
        driver_name: Annotated[str, "Driver name, surname or 3-letter code"],
        race: Annotated[str, "Race name, circuit, country, round number, or 'latest'"],
        session: SessionType,
        which: Literal["fastest", "last_q3"] = "fastest",
        lap_number: int | None = None,
    ):
        """Find one lap and its lap_id: the fastest push lap, the last Q3 push lap, or lap N."""
        race_id = resolve_race(driver, race, season, session)
        found = read_rows(
            driver,
            FIND_LAP,
            race_id=race_id,
            type=session,
            driver_id=resolve_driver(driver, driver_name),
            which=which,
            lap_number=lap_number,
        )
        if not found:
            raise LookupError(f"no matching lap for {driver_name} in {race_id} {session}")
        lap = found[0] | {"time": lap_time(found[0].pop("ms"))}
        return output("lap", lap)

    @tool(response_format="content_and_artifact")
    async def compare_laps(
        lap_a: Annotated[str, "lap_id from find_lap"], lap_b: Annotated[str, "lap_id from find_lap"]
    ):
        """Compare two laps of the same circuit: total gap and time gained or lost per corner."""
        if parse_lap_id(lap_a)[:2] != parse_lap_id(lap_b)[:2]:
            raise ValueError("both laps must be from the same race weekend")
        a_facts, b_facts = facts(lap_a), facts(lap_b)
        a, b = await asyncio.gather(store.get_lap(lap_a), store.get_lap(lap_b))
        corners = await asyncio.to_thread(load_corners, circuits_dir, a_facts["session_key"])
        gains = as_rows(corner_gains(a, b, corner_distances(a, corners)))
        distance, behind = gap(a, b)
        a_ms, b_ms = a_facts["ms"], b_facts["ms"]
        summary = {
            "a": {"lap_id": lap_a, "driver": a_facts["driver"], "time": lap_time(a_ms)},
            "b": {"lap_id": lap_b, "driver": b_facts["driver"], "time": lap_time(b_ms)},
            "b_behind_a_s": round((b_ms - a_ms) / 1000, 3),
            "biggest_corner_swings": sorted(gains, key=lambda g: -abs(g["a_gain_s"]))[:5],
        }
        data = summary | {
            "corners": gains,
            "gap": {
                "distance_m": distance[::GAP_EVERY].round(1).tolist(),
                "b_behind_a_s": behind[::GAP_EVERY].round(3).tolist(),
            },
        }
        return output("lap_compare", data, summary)

    return [find_lap, compare_laps]
