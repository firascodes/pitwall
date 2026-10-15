"""Derived graph data: Stints, TEAMMATE_OF and teammate qualifying gaps.

Derived data is calculated from Results (the source of truth). Each run deletes the
season's derived data and rebuilds it in one transaction, so it can never drift.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from statistics import mean
from typing import Any

from neo4j import Driver, ManagedTransaction

RESULTS_QUERY = """
MATCH (d:Driver)-[:ACHIEVED]->(res:Result)-[:IN_SESSION]->(s:Session)<-[:HAS_SESSION]-(r:Race),
      (res)-[:FOR_TEAM]->(t:Constructor)
WHERE r.season = $season
RETURN d.driver_id AS driver_id, t.constructor_id AS team_id, r.round AS round,
       s.session_id AS session_id, s.type AS session_type, res.result_id AS result_id,
       res.position AS position, res.classified AS classified,
       res.q1_ms AS q1_ms, res.q2_ms AS q2_ms, res.q3_ms AS q3_ms
"""


@dataclass
class Pair:
    """Head-to-head of two teammates. Index 0 is always driver a (the lower driver_id)."""

    season: int
    team: str
    a: str
    b: str
    quali_h2h: list[int] = field(default_factory=lambda: [0, 0])
    race_h2h: list[int] = field(default_factory=lambda: [0, 0])
    sprint_h2h: list[int] = field(default_factory=lambda: [0, 0])
    gaps_pct: list[float] = field(default_factory=list)  # a relative to b; negative = a faster

    def as_props(self) -> dict[str, Any]:
        return {
            "season": self.season,
            "team": self.team,
            "quali_h2h": self.quali_h2h,
            "race_h2h": self.race_h2h,
            "sprint_h2h": self.sprint_h2h,
            "avg_quali_gap_pct": round(mean(self.gaps_pct), 3) if self.gaps_pct else None,
            "sessions_together": sum(self.quali_h2h),
        }


def derive_stints(season: int, results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group each driver's rounds into stints: consecutive rounds with the same team."""
    team_by_round: dict[str, dict[int, str]] = defaultdict(dict)
    for r in results:
        team_by_round[r["driver_id"]][r["round"]] = r["team_id"]

    stints = []
    for driver_id, rounds in team_by_round.items():
        current: dict[str, Any] | None = None
        for rnd in sorted(rounds):
            team = rounds[rnd]
            if current and current["team_id"] == team:
                current["to_round"] = rnd
                continue
            current = {
                "stint_id": f"{season}-{driver_id}-{rnd:02d}",
                "season": season,
                "driver_id": driver_id,
                "team_id": team,
                "from_round": rnd,
                "to_round": rnd,
            }
            stints.append(current)
    return stints


def _quali_gap_pct(a: dict[str, Any], b: dict[str, Any]) -> float | None:
    """Gap in the last qualifying part both drivers set a time in (Q3, else Q2, else Q1).

    Uses the mean of both times as the base, so a's gap is exactly minus b's gap.
    """
    for part in ("q3_ms", "q2_ms", "q1_ms"):
        if a[part] and b[part]:
            return (a[part] - b[part]) / ((a[part] + b[part]) / 2) * 100
    return None


def derive_teammates(
    season: int, results: list[dict[str, Any]]
) -> tuple[list[Pair], dict[str, float]]:
    """Teammate pairs with head-to-heads, plus each qualifying result's gap to its teammate."""
    by_session_team: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in results:
        by_session_team[(r["session_id"], r["team_id"])].append(r)

    pairs: dict[tuple[str, str, str], Pair] = {}
    result_gaps: dict[str, float] = {}
    for (_, team), entries in by_session_team.items():
        if len(entries) != 2:
            continue  # a team ran one car (or the data is incomplete) in this session
        a, b = sorted(entries, key=lambda e: e["driver_id"])
        pair = pairs.setdefault(
            (team, a["driver_id"], b["driver_id"]),
            Pair(season=season, team=team, a=a["driver_id"], b=b["driver_id"]),
        )
        kind = a["session_type"]
        if kind == "Q":
            if a["position"] and b["position"]:
                pair.quali_h2h[0 if a["position"] < b["position"] else 1] += 1
            gap = _quali_gap_pct(a, b)
            if gap is not None:
                pair.gaps_pct.append(gap)
                result_gaps[a["result_id"]] = round(gap, 3)
                result_gaps[b["result_id"]] = round(-gap, 3)
        elif a["classified"] and b["classified"]:
            # Only compare finishing positions when both cars were classified
            h2h = pair.race_h2h if kind == "R" else pair.sprint_h2h
            h2h[0 if a["position"] < b["position"] else 1] += 1
    return list(pairs.values()), result_gaps


def _rebuild(
    tx: ManagedTransaction,
    season: int,
    stints: list[dict[str, Any]],
    pairs: list[Pair],
    gaps: dict[str, float],
) -> None:
    tx.run("MATCH (st:Stint {season: $season}) DETACH DELETE st", season=season)
    tx.run(
        """
        UNWIND $stints AS s
        MATCH (d:Driver {driver_id: s.driver_id}), (t:Constructor {constructor_id: s.team_id})
        CREATE (d)-[:HAS_STINT]->(:Stint {stint_id: s.stint_id, season: s.season,
                from_round: s.from_round, to_round: s.to_round})-[:FOR_TEAM]->(t)
        """,
        stints=stints,
    )
    tx.run("MATCH ()-[t:TEAMMATE_OF {season: $season}]->() DELETE t", season=season)
    tx.run(
        """
        UNWIND $pairs AS p
        MATCH (a:Driver {driver_id: p.a}), (b:Driver {driver_id: p.b})
        CREATE (a)-[t:TEAMMATE_OF]->(b)
        SET t = p.props
        """,
        pairs=[{"a": p.a, "b": p.b, "props": p.as_props()} for p in pairs],
    )
    tx.run(
        """
        MATCH (res:Result)-[:IN_SESSION]->(:Session {type: 'Q'})<-[:HAS_SESSION]-(r:Race)
        WHERE r.season = $season
        REMOVE res.gap_to_teammate_pct
        """,
        season=season,
    )
    tx.run(
        """
        UNWIND $gaps AS g
        MATCH (res:Result {result_id: g.result_id})
        SET res.gap_to_teammate_pct = g.gap_pct
        """,
        gaps=[{"result_id": rid, "gap_pct": gap} for rid, gap in gaps.items()],
    )


def rebuild_derived(driver: Driver, season: int) -> dict[str, int]:
    """Recalculate the season's derived data from its Results, in one transaction."""
    records, _, _ = driver.execute_query(RESULTS_QUERY, season=season)
    results = [record.data() for record in records]
    stints = derive_stints(season, results)
    pairs, gaps = derive_teammates(season, results)
    with driver.session() as session:
        session.execute_write(_rebuild, season, stints, pairs, gaps)
    return {"stints": len(stints), "teammate_pairs": len(pairs), "quali_gaps": len(gaps)}
