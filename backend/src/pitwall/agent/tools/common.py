"""Shared helpers for agent tools."""

import json
from typing import Any, Literal

Kind = Literal["rows", "h2h", "stints", "lap", "lap_compare"]
SessionType = Literal["Q", "S", "R"]
MAX_CONTENT_CHARS = 6000


def lap_time(ms: int | None) -> str | None:
    if ms is None:
        return None
    minutes, rest = divmod(ms, 60_000)
    return f"{minutes}:{rest / 1000:06.3f}" if minutes else f"{rest / 1000:.3f}"


def output(kind: Kind, data: Any, summary: Any = None) -> tuple[str, dict[str, Any]]:
    """(content for the LLM, artifact for the UI): the LLM never sees the full artifact."""
    content = json.dumps(data if summary is None else summary, default=str)
    return content[:MAX_CONTENT_CHARS], {"kind": kind, "data": data}
