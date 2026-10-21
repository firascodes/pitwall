"""Graph tools: tested Cypher templates first, guarded Text2Cypher as the fallback."""

from typing import Annotated, Literal

from langchain_core.tools import BaseTool, tool
from neo4j import Driver

from pitwall.agent.tools.common import SessionType, lap_time, output, traced
from pitwall.graph.query import read_rows, run_untrusted
from pitwall.graph.resolve import resolve_driver, resolve_race

SESSION_RESULTS = """
MATCH (:Race {race_id: $race_id})-[:HAS_SESSION]->(:Session {type: $type})
      <-[:IN_SESSION]-(res:Result)<-[:ACHIEVED]-(d:Driver),
      (res)-[:FOR_TEAM]->(t:Constructor)
RETURN res.position AS pos, d.name AS driver, t.name AS team, res.grid AS grid,
       res.points AS points, res.status AS status, res.q1_ms AS q1, res.q2_ms AS q2, res.q3_ms AS q3
ORDER BY coalesce(res.position, 99)
"""

DRIVER_SEASON = """
MATCH (:Driver {driver_id: $driver_id})-[:ACHIEVED]->(res:Result)
      -[:IN_SESSION]->(:Session {type: $type})<-[:HAS_SESSION]-(r:Race {season: $season}),
      (res)-[:FOR_TEAM]->(t:Constructor)
RETURN r.round AS round, r.name AS race, t.name AS team, res.grid AS grid, res.position AS pos,
       res.points AS points, res.status AS status, res.gap_to_teammate_pct AS gap_to_teammate_pct
ORDER BY round
"""

STANDINGS = """
MATCH (r:Race {season: $season})-[:HAS_SESSION]->(s:Session)<-[:IN_SESSION]-(res:Result),
      (d:Driver)-[:ACHIEVED]->(res)-[:FOR_TEAM]->(t:Constructor)
WHERE s.type IN ['R', 'S']
WITH CASE $by WHEN 'team' THEN t.name ELSE d.name END AS name, res, s
RETURN name, sum(res.points) AS points,
       sum(CASE WHEN s.type = 'R' AND res.position = 1 THEN 1 ELSE 0 END) AS wins
ORDER BY points DESC
"""

TEAMMATE_BATTLE = """
MATCH (me:Driver {driver_id: $driver_id})-[t:TEAMMATE_OF {season: $season}]-(mate:Driver)
// stored arrays are long[], which reverse() rejects, so swap the pair by index
WITH me, t, mate, startNode(t) = me AS mine
RETURN me.name AS driver, mate.name AS teammate, t.team AS team,
       t.sessions_together AS sessions_together,
       CASE WHEN mine THEN t.quali_h2h ELSE [t.quali_h2h[1], t.quali_h2h[0]] END AS quali_h2h,
       CASE WHEN mine THEN t.race_h2h ELSE [t.race_h2h[1], t.race_h2h[0]] END AS race_h2h,
       CASE WHEN mine THEN t.sprint_h2h ELSE [t.sprint_h2h[1], t.sprint_h2h[0]] END AS sprint_h2h,
       CASE WHEN mine THEN t.avg_quali_gap_pct ELSE -t.avg_quali_gap_pct END
         AS avg_quali_gap_pct
"""

DRIVER_TEAMS = """
MATCH (d:Driver {driver_id: $driver_id})-[:HAS_STINT]->(st:Stint {season: $season})
      -[:FOR_TEAM]->(t:Constructor)
RETURN d.name AS driver, t.name AS team, st.from_round AS from_round, st.to_round AS to_round
ORDER BY from_round
"""

SESSION_LAPS = """
MATCH (:Race {race_id: $race_id})-[:HAS_SESSION]->(:Session {type: $type})
      <-[:IN_SESSION]-(res:Result),
      (d:Driver)-[:ACHIEVED]->(res)-[:HAS_LAP]->(l:Lap)
WHERE ($driver_id IS NULL OR d.driver_id = $driver_id)
  AND ($compound IS NULL OR l.compound = $compound)
  AND CASE $only
        WHEN 'deleted' THEN l.deleted
        ELSE l.lap_time_ms IS NOT NULL AND NOT l.deleted AND NOT l.pit_in AND NOT l.pit_out
      END
RETURN l.lap_id AS lap_id, d.name AS driver, l.lap_number AS lap, l.lap_time_ms AS ms,
       l.part AS part, l.compound AS compound, l.tyre_age AS tyre_age,
       l.deleted_reason AS deleted_reason
ORDER BY CASE $only WHEN 'deleted' THEN 0 ELSE l.lap_time_ms END, lap
LIMIT 25
"""

TIME_COLUMNS = ("q1", "q2", "q3", "ms")


def _tidy(rows: list[dict]) -> list[dict]:
    """Format lap times and drop columns that are empty in every row."""
    for row in rows:
        for col in TIME_COLUMNS:
            if col in row:
                row["time" if col == "ms" else col] = lap_time(row.pop(col))
    keep = {k for row in rows for k, v in row.items() if v is not None}
    return [{k: v for k, v in row.items() if k in keep} for row in rows]


def graph_tools(driver: Driver, season: int) -> list[BaseTool]:
    def rows(cypher: str, **params) -> list[dict]:
        return _tidy(read_rows(driver, cypher, season=season, **params))

    @tool(response_format="content_and_artifact")
    @traced
    def session_results(
        race: Annotated[str, "Race name, circuit, country, round number, or 'latest'"],
        session: SessionType = "R",
    ):
        """Classification of one session: Q (qualifying), S (sprint) or R (race)."""
        race_id = resolve_race(driver, race, season, session)
        return output("rows", rows(SESSION_RESULTS, race_id=race_id, type=session))

    @tool(response_format="content_and_artifact")
    @traced
    def driver_season(
        driver_name: Annotated[str, "Driver name, surname or 3-letter code"],
        session: SessionType = "R",
    ):
        """One driver's result in every round of the season, for one session type."""
        driver_id = resolve_driver(driver, driver_name)
        return output("rows", rows(DRIVER_SEASON, driver_id=driver_id, type=session))

    @tool(response_format="content_and_artifact")
    @traced
    def standings(by: Literal["driver", "team"] = "driver"):
        """Championship standings so far: points from races and sprints, plus race wins."""
        return output("rows", rows(STANDINGS, by=by))

    @tool(response_format="content_and_artifact")
    @traced
    def teammate_battle(driver_name: Annotated[str, "Driver name, surname or 3-letter code"]):
        """Head-to-head against each teammate: [driver, teammate] wins and the qualifying gap %."""
        driver_id = resolve_driver(driver, driver_name)
        return output("h2h", rows(TEAMMATE_BATTLE, driver_id=driver_id))

    @tool(response_format="content_and_artifact")
    @traced
    def driver_teams(driver_name: Annotated[str, "Driver name, surname or 3-letter code"]):
        """The teams a driver raced for this season, with round ranges (mid-season moves)."""
        driver_id = resolve_driver(driver, driver_name)
        return output("stints", rows(DRIVER_TEAMS, driver_id=driver_id))

    @tool(response_format="content_and_artifact")
    @traced
    def session_laps(
        race: Annotated[str, "Race name, circuit, country, round number, or 'latest'"],
        session: SessionType,
        driver_name: Annotated[str | None, "Only this driver's laps"] = None,
        compound: Literal["SOFT", "MEDIUM", "HARD", "INTERMEDIATE", "WET"] | None = None,
        only: Literal["fastest", "deleted"] = "fastest",
    ):
        """Fastest push laps (or deleted laps, with the reason) in a session, max 25."""
        race_id = resolve_race(driver, race, season, session)
        driver_id = resolve_driver(driver, driver_name) if driver_name else None
        found = rows(
            SESSION_LAPS,
            race_id=race_id,
            type=session,
            driver_id=driver_id,
            compound=compound,
            only=only,
        )
        return output("rows", found)

    @tool(response_format="content_and_artifact")
    @traced
    def run_cypher(query: Annotated[str, "One read-only Cypher query that follows the schema"]):
        """Fallback for questions no other tool answers. Read-only, max 200 rows, 5 s timeout."""
        return output("rows", _tidy(run_untrusted(driver, query)))

    return [
        session_results,
        driver_season,
        standings,
        teammate_battle,
        driver_teams,
        session_laps,
        run_cypher,
    ]
