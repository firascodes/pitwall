"""Evals: lap selection (deterministic, every qualifying result) and the agent golden set (LLM)."""

import argparse
import asyncio
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from langgraph.checkpoint.memory import InMemorySaver
from neo4j import Driver

from pitwall.agent.tools.laps import FIND_LAP
from pitwall.api.ask import new_meter, run
from pitwall.config import get_settings
from pitwall.evals.golden import CASES, Case
from pitwall.graph.db import connect
from pitwall.graph.query import read_rows

RESULTS = Path(__file__).parents[3] / "evals" / "results"

QUALI_RESULTS = """
MATCH (r:Race {season: $season})-[:HAS_SESSION]->(:Session {type: 'Q'})<-[:IN_SESSION]-(res:Result),
      (d:Driver)-[:ACHIEVED]->(res)
WHERE (res)-[:HAS_LAP]->()
WITH r, d, [t IN [res.q1_ms, res.q2_ms, res.q3_ms] WHERE t IS NOT NULL] AS times
WHERE size(times) > 0
RETURN r.race_id AS race_id, d.driver_id AS driver_id,
       reduce(best = times[0], t IN times | CASE WHEN t < best THEN t ELSE best END) AS official_ms
ORDER BY race_id, driver_id
"""


def lap_selection(graph: Driver, season: int) -> dict[str, Any]:
    """find_lap's 'fastest' lap must be the driver's official best qualifying time."""
    misses = []
    rows = read_rows(graph, QUALI_RESULTS, season=season)
    for row in rows:
        params = {"type": "Q", "which": "fastest", "lap_number": None}
        found = read_rows(
            graph, FIND_LAP, **params, race_id=row["race_id"], driver_id=row["driver_id"]
        )
        got = found[0]["ms"] if found else None
        if got is None or abs(got - row["official_ms"]) > 1:
            misses.append(row | {"find_lap_ms": got})
    return {
        "name": "lap_selection",
        "cases": len(rows),
        "accuracy": round(1 - len(misses) / len(rows), 4),
        "misses": misses,
    }


async def ask_case(agent: Any, case: Case, i: int) -> dict[str, Any]:
    tools, blocks, usage, started = [], [], {}, time.perf_counter()
    async for event, data in run(agent, case.question, f"eval-{i}", new_meter()):
        if event == "tool" and data["ok"]:
            tools.append(data["name"])
        elif event == "block":
            blocks.append(data)
        elif event == "done":
            usage = data["usage"]
    text = " ".join(b["text"] for b in blocks if b["type"] == "text").lower()
    shown = {b["type"] for b in blocks} - {"text", "chips"}
    checks = {
        "tools": case.tools <= set(tools),
        "facts": all(any(o.lower() in text for o in f.split("|")) for f in case.facts),
        "components": case.components <= shown,
    }
    return {
        "question": case.question,
        "pass": all(checks.values()),
        **checks,
        "called": tools,
        "shown": sorted(shown),
        "usd": usage.get("usd", 0),
        "llm_calls": usage.get("llm_calls", 0),
        "seconds": round(time.perf_counter() - started, 1),
        "answer": text[:400],
    }


async def agent_golden(graph: Driver, limit: int | None) -> dict[str, Any]:
    from pitwall.agent.factory import create_agent
    from pitwall.telemetry.source import openf1_lap_loader
    from pitwall.telemetry.store import TelemetryStore

    s = get_settings()
    store = TelemetryStore(s.telemetry_dir, openf1_lap_loader(graph))
    agent = create_agent(s, graph, store, InMemorySaver())
    cases = [await ask_case(agent, c, i) for i, c in enumerate(CASES[:limit])]
    n = len(cases)
    rate = lambda key: round(sum(c[key] for c in cases) / n, 3)  # noqa: E731
    seconds = sorted(c["seconds"] for c in cases)
    return {
        "name": "agent_golden",
        "model": s.llm_model,
        "cases": n,
        "pass_rate": rate("pass"),
        "tool_accuracy": rate("tools"),
        "fact_accuracy": rate("facts"),
        "component_accuracy": rate("components"),
        "usd_total": round(sum(c["usd"] for c in cases), 6),
        "p50_seconds": seconds[n // 2],
        "p95_seconds": seconds[min(n - 1, round(n * 0.95))],
        "results": cases,
    }


def save(report: dict[str, Any]) -> None:
    RESULTS.mkdir(parents=True, exist_ok=True)
    report["ran_at"] = datetime.now(UTC).isoformat(timespec="seconds")
    (RESULTS / f"{report['name']}.json").write_text(json.dumps(report, indent=2) + "\n")
    summary = {k: v for k, v in report.items() if k not in {"results", "misses"}}
    print(json.dumps(summary, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(prog="pitwall-eval")
    parser.add_argument("suite", choices=["laps", "agent"])
    parser.add_argument("--limit", type=int, help="only the first N agent cases")
    args = parser.parse_args()
    graph = connect()
    try:
        if args.suite == "laps":
            save(lap_selection(graph, get_settings().season))
        else:
            save(asyncio.run(agent_golden(graph, args.limit)))
    finally:
        graph.close()
