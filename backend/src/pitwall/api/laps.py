"""GET /laps/{lap_id}: one lap's resampled telemetry, for the replay component."""

import polars as pl
from fastapi import APIRouter, HTTPException, Request

from pitwall.telemetry.laps import parse_lap_id

router = APIRouter()
COLUMNS = ("distance_m", "time_s", "x_m", "y_m", "speed_kph", "throttle_pct", "gear", "brake")


@router.get("/laps/{lap_id}")
async def lap(lap_id: str, request: Request) -> dict:
    try:
        parse_lap_id(lap_id)
        frame = await request.app.state.store.get_lap(lap_id)
    except (ValueError, LookupError) as e:
        raise HTTPException(404, f"no telemetry for lap {lap_id}") from e
    columns = {
        c: frame[c].cast(pl.Float64).round(3) if frame[c].dtype.is_float() else frame[c]
        for c in COLUMNS
    }
    return {"lap_id": lap_id, **{c: s.to_list() for c, s in columns.items()}}
