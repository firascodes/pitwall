"""Lap telemetry on disk: one Parquet file per lap, filled eagerly (hot set) or on demand."""

import asyncio
import logging
import os
from collections.abc import Callable
from pathlib import Path

import polars as pl

from pitwall.telemetry.laps import parse_lap_id
from pitwall.telemetry.locks import SessionLock, no_lock

log = logging.getLogger(__name__)

# Loads one lap's resampled telemetry from the source. Blocking (network I/O).
LapLoader = Callable[[str], pl.DataFrame]


def lap_path(root: Path, lap: str) -> Path:
    season, rnd, session_type, driver_id, number = parse_lap_id(lap)
    return root / str(season) / f"{rnd:02d}" / session_type / driver_id / f"{number:02d}.parquet"


def write_lap(root: Path, lap: str, frame: pl.DataFrame) -> Path:
    """Atomic write: readers see the old state or the full new file, never half a file."""
    path = lap_path(root, lap)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".parquet.tmp")
    frame.write_parquet(tmp, compression="zstd")
    os.replace(tmp, path)  # a rename is atomic on the same filesystem
    return path


class TelemetryStore:
    """Cache-aside access to lap telemetry, safe under concurrent requests.

    1. Fast path: the Parquet file exists -> read it.
    2. Single-flight (in this process, key = lap): concurrent requests share one load.
    3. Advisory lock (across processes, key = session): one download per session at a time.
    4. Double-check after the lock: another worker may have written the file meanwhile.
    """

    def __init__(self, root: Path, loader: LapLoader, lock: SessionLock = no_lock) -> None:
        self.root = root
        self._loader = loader
        self._lock = lock
        self._inflight: dict[str, asyncio.Task[pl.DataFrame]] = {}

    async def get_lap(self, lap: str) -> pl.DataFrame:
        path = lap_path(self.root, lap)
        if path.exists():
            return pl.read_parquet(path)
        task = self._inflight.get(lap)
        if task is None:
            task = asyncio.create_task(self._load(lap))
            self._inflight[lap] = task
            task.add_done_callback(lambda _: self._inflight.pop(lap, None))
        return await task

    async def _load(self, lap: str) -> pl.DataFrame:
        season, rnd, session_type, _, _ = parse_lap_id(lap)
        async with self._lock(f"session:{season}-{rnd:02d}-{session_type}"):
            path = lap_path(self.root, lap)
            if path.exists():  # double-checked locking
                return pl.read_parquet(path)
            log.info("telemetry cache miss for %s, loading from source", lap)
            frame = await asyncio.to_thread(self._loader, lap)  # don't block the event loop
            write_lap(self.root, lap, frame)
            return frame
