"""Corner positions for a session's circuit, cached on disk (they never change)."""

import json
from dataclasses import dataclass
from pathlib import Path

import httpx
import numpy as np
import polars as pl

from pitwall.sources.openf1 import OpenF1Client

MULTIVIEWER_URL = "https://api.multiviewer.app/api/v1/circuits/{key}/{year}"


@dataclass(frozen=True)
class Corner:
    number: int
    letter: str
    x_m: float
    y_m: float

    @property
    def label(self) -> str:
        return f"T{self.number}{self.letter}"


def fetch_corners(session_key: int, client: OpenF1Client) -> list[Corner]:
    session = client.get("sessions", session_key=session_key)[0]
    url = MULTIVIEWER_URL.format(key=session["circuit_key"], year=session["year"])
    data = httpx.get(url, headers={"User-Agent": "pitwall"}, timeout=30).raise_for_status().json()
    return [
        Corner(
            c["number"],
            c.get("letter") or "",
            c["trackPosition"]["x"] / 10,
            c["trackPosition"]["y"] / 10,
        )
        for c in data["corners"]
    ]


def load_corners(root: Path, session_key: int, client: OpenF1Client | None = None) -> list[Corner]:
    path = root / f"session-{session_key}.json"
    if not path.exists():
        corners = fetch_corners(session_key, client or OpenF1Client())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps([c.__dict__ for c in corners]))
    return [Corner(**c) for c in json.loads(path.read_text())]


def corner_distances(lap: pl.DataFrame, corners: list[Corner]) -> list[tuple[Corner, float]]:
    """Place each corner on the lap: the distance of the nearest point on the racing line."""
    x, y, distance = (lap[c].to_numpy() for c in ("x_m", "y_m", "distance_m"))
    placed = [(c, float(distance[np.argmin((x - c.x_m) ** 2 + (y - c.y_m) ** 2)])) for c in corners]
    return sorted(placed, key=lambda p: p[1])
