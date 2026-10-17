import asyncio
import threading
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import polars as pl

from pitwall.telemetry.openf1_telemetry import build_lap_frame
from pitwall.telemetry.resample import resample_lap
from pitwall.telemetry.store import TelemetryStore, lap_path, write_lap

START = datetime.fromisoformat("2026-10-10T14:20:00+00:00")
LAP = "2026-17-Q-hamilton-21"


def _samples(n: int, every_s: float, **fields) -> list[dict]:
    return [
        {
            "date": (START + timedelta(seconds=i * every_s)).isoformat(),
            **{k: v(i) for k, v in fields.items()},
        }
        for i in range(n)
    ]


def test_distance_is_integrated_speed_and_position_is_aligned() -> None:
    car = _samples(
        41,
        0.25,
        speed=lambda i: 180,
        rpm=lambda i: 11000,
        throttle=lambda i: 100,
        n_gear=lambda i: 7,
        brake=lambda i: 0,
    )
    loc = _samples(
        41, 0.25, x=lambda i: i * 125.0, y=lambda i: 0.0
    )  # offset sampling would still align

    frame = build_lap_frame(car, loc, START)

    assert frame["Distance"].iloc[-1] == np.float64(500.0)  # 180 km/h = 50 m/s for 10 s
    assert frame["X"].iloc[20] == 2500.0


def test_resample_holds_gear_and_interpolates_speed() -> None:
    tel = pd.DataFrame(
        {
            "Time": pd.to_timedelta([0.0, 1.0, 2.0], unit="s"),
            "Distance": [0.0, 10.0, 20.0],
            "X": [0, 100, 200],
            "Y": [0, 0, 0],
            "Speed": [100.0, 200.0, 300.0],
            "RPM": [10000, 11000, 12000],
            "Throttle": [100, 100, 100],
            "nGear": [5, 6, 7],
            "Brake": [False, False, True],
        }
    )

    out = resample_lap(tel, LAP, step_m=5.0)

    assert out["distance_m"].to_list() == [0.0, 5.0, 10.0, 15.0]
    assert out["speed_kph"].to_list() == [100.0, 150.0, 200.0, 250.0]
    assert out["gear"].to_list() == [5, 5, 6, 6]  # held, never 5.5


def test_concurrent_cache_misses_load_once(tmp_path) -> None:
    calls = 0
    gate = threading.Event()

    def slow_loader(lap: str) -> pl.DataFrame:
        nonlocal calls
        calls += 1
        gate.wait(timeout=5)
        return pl.DataFrame({"lap_id": [lap], "distance_m": [0.0]})

    store = TelemetryStore(tmp_path, slow_loader)

    async def scenario() -> list[pl.DataFrame]:
        tasks = [asyncio.create_task(store.get_lap(LAP)) for _ in range(3)]
        await asyncio.sleep(0.05)
        gate.set()
        return await asyncio.gather(*tasks)

    results = asyncio.run(scenario())

    assert calls == 1  # single-flight: three requests, one load
    assert all(r.equals(results[0]) for r in results)
    assert lap_path(tmp_path, LAP).exists()


def test_cache_hit_skips_the_loader(tmp_path) -> None:
    write_lap(tmp_path, LAP, pl.DataFrame({"distance_m": [0.0]}))

    def loader(lap: str) -> pl.DataFrame:
        raise AssertionError("should not load on a cache hit")

    assert asyncio.run(TelemetryStore(tmp_path, loader).get_lap(LAP)).height == 1
