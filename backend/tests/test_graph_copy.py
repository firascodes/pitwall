from pitwall.graph.copy import RELATIONSHIPS
from pitwall.graph.schema import UNIQUE_KEYS


def test_every_relationship_endpoint_has_a_unique_key(graph) -> None:
    rows = graph.execute_query(RELATIONSHIPS, keys=UNIQUE_KEYS).records
    total = graph.execute_query("MATCH ()-[r]->() RETURN count(r) AS n").records[0]["n"]
    assert len(rows) == total
    assert not [r for r in rows if r["ka"] is None or r["kb"] is None]
