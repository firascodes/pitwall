"""Compare two laps on the shared 5 m distance grid: running gap and corner-by-corner gains."""

from dataclasses import asdict, dataclass

import numpy as np
import polars as pl

from pitwall.telemetry.corners import Corner

MIN_BRAKE_DIFF_M = 5.0
MIN_SPEED_DIFF_KPH = 2.0


@dataclass(frozen=True)
class CornerGain:
    corner: str
    distance_m: float
    a_gain_s: float  # positive: lap A gained time here
    a_min_kph: float
    b_min_kph: float
    a_brake_m: float | None
    b_brake_m: float | None
    cause: str


def gap(a: pl.DataFrame, b: pl.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Distance and B's time behind A at each point (positive: B is behind), from 0 at the line."""
    n = min(a.height, b.height)
    behind = b["time_s"].to_numpy()[:n] - a["time_s"].to_numpy()[:n]
    return a["distance_m"].to_numpy()[:n], behind - behind[0]


def _stats(lap: pl.DataFrame, lo: int, hi: int) -> dict[str, float | None]:
    speed, brake, distance = (lap[c].to_numpy() for c in ("speed_kph", "brake", "distance_m"))
    braking = np.flatnonzero(brake[lo:hi])
    return {
        "min": float(speed[lo:hi].min()),
        "exit": float(speed[hi]),
        "brake": float(distance[lo + braking[0]]) if braking.size else None,
    }


def _cause(a_gain: float, a: dict[str, float | None], b: dict[str, float | None]) -> str:
    fast, slow = (a, b) if a_gain > 0 else (b, a)
    if fast["brake"] and slow["brake"] and fast["brake"] - slow["brake"] >= MIN_BRAKE_DIFF_M:
        return "later braking"
    if fast["min"] - slow["min"] >= MIN_SPEED_DIFF_KPH:
        return "higher minimum speed"
    if fast["exit"] - slow["exit"] >= MIN_SPEED_DIFF_KPH:
        return "better exit"
    return "small gains through the corner"


def corner_gains(
    a: pl.DataFrame, b: pl.DataFrame, placed: list[tuple[Corner, float]]
) -> list[CornerGain]:
    """Split the lap at the midpoints between corners and measure the gap change in each part."""
    distance, behind = gap(a, b)
    centres = [d for _, d in placed]
    edges = [0.0, *((x + y) / 2 for x, y in zip(centres, centres[1:], strict=False)), distance[-1]]
    gains = []
    for (corner, centre), lo_m, hi_m in zip(placed, edges, edges[1:], strict=False):
        lo, hi = np.searchsorted(distance, [lo_m, hi_m])
        hi = min(max(hi, lo + 1), len(distance) - 1)
        a_gain = float(behind[hi] - behind[lo])
        stats = [_stats(lap, int(lo), int(hi)) for lap in (a, b)]
        gains.append(
            CornerGain(
                corner=corner.label,
                distance_m=centre,
                a_gain_s=round(a_gain, 3),
                a_min_kph=round(stats[0]["min"], 1),
                b_min_kph=round(stats[1]["min"], 1),
                a_brake_m=stats[0]["brake"],
                b_brake_m=stats[1]["brake"],
                cause=_cause(a_gain, *stats),
            )
        )
    return gains


def as_rows(gains: list[CornerGain]) -> list[dict]:
    return [asdict(g) for g in gains]
