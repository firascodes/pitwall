"""Shared helpers for agent tools."""

import functools
import inspect
import json
from collections.abc import Callable
from typing import Any, Literal

from pitwall.graph.query import recording

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


def traced(fn: Callable) -> Callable:
    """Attach the Cypher queries a tool ran to its artifact, so the trace can show them."""
    if inspect.iscoroutinefunction(fn):

        @functools.wraps(fn)
        async def run_async(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
            with recording() as queries:
                content, artifact = await fn(*args, **kwargs)
            return content, artifact | {"queries": queries}

        return run_async

    @functools.wraps(fn)
    def run(*args: Any, **kwargs: Any) -> tuple[str, dict[str, Any]]:
        with recording() as queries:
            content, artifact = fn(*args, **kwargs)
        return content, artifact | {"queries": queries}

    return run
