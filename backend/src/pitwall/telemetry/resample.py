"""Resample one lap of telemetry onto a fixed distance grid."""

import numpy as np
import pandas as pd
import polars as pl

STEP_M = 5.0

# Continuous channels: linear interpolation is correct between samples
CONTINUOUS = {"Speed": "speed_kph", "RPM": "rpm", "Throttle": "throttle_pct"}
# Step channels: hold the last known value (gear 5.4 or brake 0.5 make no sense)
STEPPED = {"nGear": "gear", "Brake": "brake"}


def resample_lap(telemetry: pd.DataFrame, lap_id: str, step_m: float = STEP_M) -> pl.DataFrame:
    """FastF1 merged lap telemetry (with Distance, X, Y) -> one row per `step_m` metres.

    Distance-indexed rows make lap comparison simple: row n of two laps is the same
    place on the track, so the time delta is a subtraction.
    """
    tel = telemetry.dropna(subset=["Distance", "X", "Y", "Speed"])
    distance, first = np.unique(tel["Distance"].to_numpy(dtype=float), return_index=True)
    tel = tel.iloc[first]  # Distance must be strictly increasing for interpolation
    grid = np.arange(0.0, distance[-1], step_m)

    columns: dict[str, np.ndarray] = {
        "distance_m": grid,
        "time_s": np.interp(grid, distance, tel["Time"].dt.total_seconds().to_numpy()),
        "x_m": np.interp(grid, distance, tel["X"].to_numpy(dtype=float) / 10),  # FastF1: 1/10 m
        "y_m": np.interp(grid, distance, tel["Y"].to_numpy(dtype=float) / 10),
    }
    for source, name in CONTINUOUS.items():
        columns[name] = np.interp(grid, distance, tel[source].to_numpy(dtype=float))

    last_before = np.clip(np.searchsorted(distance, grid, side="right") - 1, 0, len(distance) - 1)
    columns["gear"] = tel["nGear"].to_numpy()[last_before].astype(np.int8)
    columns["brake"] = tel["Brake"].to_numpy()[last_before].astype(bool)

    return pl.DataFrame(columns).with_columns(
        pl.lit(lap_id).alias("lap_id"),
        pl.col("speed_kph", "rpm", "throttle_pct").cast(pl.Float32),
        pl.col("x_m", "y_m").cast(pl.Float32),
    )
