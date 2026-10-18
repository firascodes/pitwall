"""Entity resolution: free text from the user or the LLM -> graph IDs."""

from neo4j import Driver

from pitwall.graph.query import read_rows

LATEST = {"latest", "last", "most recent", "recent"}

# Ranked: exact id or code beats a whole word of the name, which beats a substring
DRIVER_QUERY = """
MATCH (d:Driver)
WITH d, CASE
  WHEN d.driver_id = $q OR toLower(d.code) = $q THEN 2
  WHEN $q IN split(toLower(d.name), ' ') OR toLower(d.name) = $q THEN 1
  WHEN toLower(d.name) CONTAINS $q THEN 0
END AS score
WHERE score IS NOT NULL
RETURN d.driver_id AS id, d.name AS name, score ORDER BY score DESC, name
"""

RACE_QUERY = """
MATCH (r:Race {season: $season})-[:AT]->(c:Circuit)
WHERE r.round = $round OR toLower(r.name) CONTAINS $q OR toLower(c.name) CONTAINS $q
   OR toLower(c.locality) CONTAINS $q OR toLower(c.country) CONTAINS $q
RETURN r.race_id AS id, r.name AS name ORDER BY r.round
"""

LATEST_RACE_QUERY = """
MATCH (r:Race {season: $season})-[:HAS_SESSION]->(s:Session)<-[:IN_SESSION]-(:Result)
WHERE $session IS NULL OR s.type = $session
RETURN r.race_id AS id, r.name AS name ORDER BY r.round DESC LIMIT 1
"""


def _one(rows: list[dict], kind: str, text: str) -> str:
    rows = [r for r in rows if r.get("score", 0) == rows[0].get("score", 0)] if rows else rows
    if not rows:
        raise LookupError(f"no {kind} matches '{text}'")
    if len(rows) > 1:
        names = ", ".join(r["name"] for r in rows)
        raise LookupError(f"'{text}' is ambiguous, it matches: {names}. Ask the user which one.")
    return rows[0]["id"]


def resolve_driver(driver: Driver, text: str) -> str:
    q = text.strip().lower()
    return _one(read_rows(driver, DRIVER_QUERY, q=q), "driver", text)


def resolve_race(driver: Driver, text: str, season: int, session: str | None = None) -> str:
    q = text.strip().lower()
    if q in LATEST:
        return _one(
            read_rows(driver, LATEST_RACE_QUERY, season=season, session=session), "race", text
        )
    rnd = int(q) if q.isdigit() else -1
    return _one(read_rows(driver, RACE_QUERY, season=season, round=rnd, q=q), "race", text)
