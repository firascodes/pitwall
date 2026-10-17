"""On-demand loading of one lap's telemetry (the cache-miss path of TelemetryStore)."""

import polars as pl
from neo4j import Driver

from pitwall.sources.openf1 import OpenF1Client
from pitwall.telemetry.openf1_telemetry import build_lap_frame, lap_window
from pitwall.telemetry.resample import resample_lap
from pitwall.telemetry.store import LapLoader

LAP_QUERY = """
MATCH (s:Session)<-[:IN_SESSION]-(:Result)-[:HAS_LAP]->(l:Lap {lap_id: $lap_id})
RETURN s.openf1_session_key AS session_key, l.driver_number AS driver_number,
       l.started_at AS started_at, l.lap_time_ms AS lap_time_ms
"""


def openf1_lap_loader(driver: Driver, client: OpenF1Client | None = None) -> LapLoader:
    client = client or OpenF1Client()

    def load(lap: str) -> pl.DataFrame:
        records, _, _ = driver.execute_query(LAP_QUERY, lap_id=lap)
        if not records or records[0]["lap_time_ms"] is None or records[0]["session_key"] is None:
            raise LookupError(f"no timed lap {lap} in the graph")
        rec = records[0]
        start, end = lap_window(rec["started_at"].to_native(), rec["lap_time_ms"])
        car = client.car_data(rec["session_key"], rec["driver_number"], start, end)
        loc = client.location(rec["session_key"], rec["driver_number"], start, end)
        return resample_lap(build_lap_frame(car, loc, start), lap)

    return load
