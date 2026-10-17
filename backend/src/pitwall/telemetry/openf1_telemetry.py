"""OpenF1 car data + location for one lap -> the frame `resample_lap` expects."""

from datetime import datetime, timedelta
from typing import Any

import numpy as np
import pandas as pd


def build_lap_frame(
    car_data: list[dict[str, Any]], location: list[dict[str, Any]], lap_start: datetime
) -> pd.DataFrame:
    """Merge two streams sampled at different moments, and add distance.

    - Position is interpolated onto the car-data timestamps (time-series alignment).
    - Distance is speed integrated over time (trapezoid rule); OpenF1 has no distance channel.
    """
    car = pd.DataFrame(car_data)
    loc = pd.DataFrame(location)
    if car.empty or loc.empty:
        raise ValueError("no telemetry for this lap window")

    car_t = (
        (pd.to_datetime(car["date"], format="ISO8601") - lap_start).dt.total_seconds().to_numpy()
    )
    loc_t = (
        (pd.to_datetime(loc["date"], format="ISO8601") - lap_start).dt.total_seconds().to_numpy()
    )
    order = np.argsort(car_t)
    car, car_t = car.iloc[order].reset_index(drop=True), car_t[order]
    loc_order = np.argsort(loc_t)
    loc, loc_t = loc.iloc[loc_order], loc_t[loc_order]

    speed_ms = car["speed"].to_numpy(dtype=float) / 3.6
    distance = np.concatenate(
        [[0.0], np.cumsum((speed_ms[1:] + speed_ms[:-1]) / 2 * np.diff(car_t))]
    )

    return pd.DataFrame(
        {
            "Time": pd.to_timedelta(car_t, unit="s"),
            "Distance": distance,
            "X": np.interp(car_t, loc_t, loc["x"].to_numpy(dtype=float)),
            "Y": np.interp(car_t, loc_t, loc["y"].to_numpy(dtype=float)),
            "Speed": car["speed"].to_numpy(dtype=float),
            "RPM": car["rpm"].to_numpy(dtype=float),
            "Throttle": car["throttle"].to_numpy(dtype=float),
            "nGear": car["n_gear"].to_numpy(dtype=int),
            "Brake": car["brake"].to_numpy(dtype=float) > 0,  # OpenF1 brake is 0 or 100
        }
    )


def lap_window(started_at: datetime | str, lap_time_ms: int) -> tuple[datetime, datetime]:
    start = datetime.fromisoformat(started_at) if isinstance(started_at, str) else started_at
    return start, start + timedelta(milliseconds=lap_time_ms)


def slice_window(
    rows: list[dict[str, Any]], start: datetime, end: datetime
) -> list[dict[str, Any]]:
    """Samples inside [start, end], from a bigger downloaded window."""
    return [r for r in rows if start <= datetime.fromisoformat(r["date"]) <= end]
