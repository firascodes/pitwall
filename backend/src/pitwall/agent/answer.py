"""Hybrid answers: the composer drafts blocks, code validates them and fills in the data."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field

from pitwall.agent.tools.common import Kind

Component = Literal[
    "results_table", "h2h_card", "stint_timeline", "lap_replay", "delta_chart", "corner_table"
]
MAX_COMPONENTS = 4
MAX_CHIPS = 3

# Which components each kind of tool result can fill
FILLS: dict[Kind, set[str]] = {
    "rows": {"results_table"},
    "h2h": {"h2h_card", "results_table"},
    "stints": {"stint_timeline", "results_table"},
    "lap": {"lap_replay"},
    "lap_compare": {"lap_replay", "delta_chart", "corner_table"},
}


class TextDraft(BaseModel):
    type: Literal["text"]
    text: str = Field(description="Short markdown. Cite sources inline like [r1].")


class ComponentDraft(BaseModel):
    type: Literal["component"]
    component: Component
    source: str = Field(description="The id of the tool result that fills it, e.g. r1")
    title: str


class ChipsDraft(BaseModel):
    type: Literal["chips"]
    options: list[str] = Field(description="Up to 3 short follow-up questions")


class Draft(BaseModel):
    blocks: list[TextDraft | ComponentDraft | ChipsDraft]  # anyOf: OpenAI strict mode rejects oneOf


@dataclass(frozen=True)
class Source:
    id: str
    tool: str
    kind: Kind
    data: Any
    content: str


def _replay(kind: Kind, data: Any) -> dict[str, Any]:
    laps = [data] if kind == "lap" else [data["a"], data["b"]]
    return {
        "laps": [lap["lap_id"] for lap in laps],
        "drivers": [lap["driver"] for lap in laps],
        "times": [lap["time"] for lap in laps],
        "sectors_ms": [lap.get("sectors_ms") for lap in laps],
        "ghost": kind == "lap_compare",
    }


def _weekend(lap_id: str) -> str:
    return lap_id.rsplit("-", 2)[0]  # '2026-17-Q-hamilton-21' -> '2026-17-Q'


def _merge(replay: dict[str, Any], lap: dict[str, Any]) -> bool:
    """Two single-lap replays of one session become one replay with both cars."""
    data = replay["data"]
    if len(data["laps"]) != 1 or _weekend(data["laps"][0]) != _weekend(lap["laps"][0]):
        return False
    for key in ("laps", "drivers", "times", "sectors_ms"):
        data[key] = data[key] + lap[key]
    data["ghost"] = True
    return True


FILL: dict[str, Callable[[Kind, Any], Any]] = {
    "results_table": lambda _, data: {"rows": data},
    "h2h_card": lambda _, data: {"rows": data},
    "stint_timeline": lambda _, data: {"stints": data},
    "lap_replay": _replay,
    "delta_chart": lambda _, data: data["gap"] | {"a": data["a"], "b": data["b"]},
    "corner_table": lambda _, data: {"rows": data["corners"], "a": data["a"], "b": data["b"]},
}


def hydrate(draft: Draft, sources: dict[str, Source]) -> list[dict[str, Any]]:
    """Keep only components that a real, matching, non-empty tool result can fill."""
    blocks: list[dict[str, Any]] = []
    components = 0
    for block in draft.blocks:
        if isinstance(block, TextDraft) and block.text.strip():
            blocks.append({"type": "text", "text": block.text})
        elif isinstance(block, ChipsDraft) and block.options:
            blocks.append({"type": "chips", "options": block.options[:MAX_CHIPS]})
        elif isinstance(block, ComponentDraft):
            source = sources.get(block.source)
            if (
                source is None
                or not source.data
                or block.component not in FILLS[source.kind]
                or components == MAX_COMPONENTS
            ):
                continue
            data = FILL[block.component](source.kind, source.data)
            if block.component == "lap_replay":
                earlier = next((b for b in blocks if b["type"] == "lap_replay"), None)
                if earlier and _merge(earlier, data):
                    continue
            blocks.append(
                {"type": block.component, "title": block.title, "source": source.id, "data": data}
            )
            components += 1
    return blocks


def catalog(sources: dict[str, Source]) -> str:
    """The tool results the composer may use, and which components each one can fill."""
    return "\n\n".join(
        f"[{s.id}] {s.tool} -> can fill: {', '.join(sorted(FILLS[s.kind]))}\n{s.content}"
        for s in sources.values()
    )
