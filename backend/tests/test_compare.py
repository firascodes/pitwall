import numpy as np
import polars as pl

from pitwall.telemetry.compare import corner_gains, gap
from pitwall.telemetry.corners import Corner, corner_distances


def _lap(time_s: np.ndarray, speed: np.ndarray, brake_at: float) -> pl.DataFrame:
    distance = np.arange(len(time_s)) * 5.0
    return pl.DataFrame(
        {
            "distance_m": distance,
            "time_s": time_s,
            "x_m": distance,
            "y_m": np.zeros_like(distance),
            "speed_kph": speed,
            "brake": (distance >= brake_at) & (distance < brake_at + 50),
        }
    )


def test_corner_gains_add_up_to_the_lap_gap_and_name_the_cause() -> None:
    n = 200  # a 1 km straight line with two corners
    a = _lap(np.linspace(0, 20, n), np.full(n, 200.0), brake_at=300)
    b_time = np.linspace(0, 20, n)
    b_time[60:] += 0.15  # B loses 0.15 s around the first corner (it brakes earlier)
    b = _lap(b_time, np.full(n, 200.0), brake_at=250)
    placed = corner_distances(a, [Corner(1, "", 350, 0), Corner(2, "", 800, 0)])

    gains = corner_gains(a, b, placed)

    assert [g.corner for g in gains] == ["T1", "T2"]
    assert gains[0].a_gain_s == 0.15 and gains[0].cause == "later braking"
    assert gains[1].a_gain_s == 0.0
    assert round(sum(g.a_gain_s for g in gains), 3) == round(float(gap(a, b)[1][-1]), 3)


def test_corner_distances_snap_corners_to_the_racing_line() -> None:
    lap = _lap(np.linspace(0, 20, 200), np.full(200, 200.0), brake_at=0)
    [(corner, distance)] = corner_distances(lap, [Corner(7, "a", 502, 3)])
    assert corner.label == "T7a" and distance == 500.0
