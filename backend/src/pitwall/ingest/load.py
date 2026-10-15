"""Write typed rows to Neo4j with batched, idempotent Cypher (UNWIND + MERGE)."""

from collections.abc import Iterator, Sequence

from neo4j import Driver
from pydantic import BaseModel

BATCH_SIZE = 500

# Every node is MERGEd on its own key first, then relationships are MERGEd between
# bound nodes. MERGE on a whole pattern would create duplicate nodes when part of it is new.
RACES_CYPHER = """
UNWIND $rows AS row
MERGE (c:Circuit {circuit_id: row.circuit_id})
  SET c.name = row.circuit_name, c.locality = row.locality, c.country = row.country,
      c.location = point({latitude: row.lat, longitude: row.lng})
MERGE (r:Race {race_id: row.race_id})
  SET r.season = row.season, r.round = row.round, r.name = row.name,
      r.date = date(row.date), r.url = row.url
MERGE (r)-[:AT]->(c)
WITH r, row
UNWIND row.sessions AS s
MERGE (ses:Session {session_id: s.session_id})
  SET ses.type = s.type, ses.starts_at = datetime(s.starts_at)
MERGE (r)-[:HAS_SESSION]->(ses)
"""

RESULTS_CYPHER = """
UNWIND $rows AS row
MERGE (d:Driver {driver_id: row.driver.driver_id})
  SET d.code = row.driver.code, d.name = row.driver.name,
      d.nationality = row.driver.nationality, d.dob = date(row.driver.dob),
      d.number = row.driver.number
MERGE (t:Constructor {constructor_id: row.constructor.constructor_id})
  SET t.name = row.constructor.name, t.nationality = row.constructor.nationality
WITH row, d, t
MATCH (s:Session {session_id: row.session_id})
MERGE (res:Result {result_id: row.result_id})
  SET res += row.props
MERGE (d)-[:ACHIEVED]->(res)
MERGE (res)-[:IN_SESSION]->(s)
WITH res, t
// MERGE never removes anything: drop a stale team link if the source data was corrected
OPTIONAL MATCH (res)-[old:FOR_TEAM]->(other:Constructor)
  WHERE other <> t
DELETE old
MERGE (res)-[:FOR_TEAM]->(t)
"""


def batched[T](items: Sequence[T], size: int = BATCH_SIZE) -> Iterator[Sequence[T]]:
    for start in range(0, len(items), size):
        yield items[start : start + size]


def write_rows(driver: Driver, cypher: str, rows: Sequence[BaseModel]) -> int:
    for batch in batched(rows):
        driver.execute_query(cypher, rows=[row.model_dump() for row in batch])
    return len(rows)
