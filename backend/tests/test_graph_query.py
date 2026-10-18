import pytest
from neo4j.exceptions import CypherSyntaxError

from pitwall.graph.query import MAX_ROWS, UnsafeCypher, read_rows, run_untrusted


def test_reads_rows_as_plain_values(graph) -> None:
    rows = read_rows(
        graph, "MATCH (r:Race {round: $rnd}) RETURN r.name AS name, r.date AS d", rnd=17
    )
    assert rows == [{"name": "Singapore Grand Prix", "d": rows[0]["d"]}]
    assert isinstance(rows[0]["d"], str)


@pytest.mark.parametrize(
    "cypher",
    [
        "CREATE (x:Hack) RETURN x",
        "MATCH (d:Driver) SET d.hacked = true",
        "MATCH (n) DETACH DELETE n",
        "LOAD CSV FROM 'http://169.254.169.254/latest' AS row RETURN row",
        "CALL apoc.load.json('file:///etc/passwd')",
        "PROFILE MATCH (n) RETURN n",
    ],
)
def test_untrusted_cypher_cannot_write_or_reach_out(graph, cypher: str) -> None:
    with pytest.raises(UnsafeCypher):
        run_untrusted(graph, cypher)
    assert read_rows(graph, "MATCH (x:Hack) RETURN count(x) AS n") == [{"n": 0}]


def test_untrusted_cypher_returns_capped_rows(graph) -> None:
    assert len(run_untrusted(graph, "MATCH (l:Lap) RETURN l.lap_id AS id")) == MAX_ROWS


def test_syntax_errors_surface_for_the_agent_to_fix(graph) -> None:
    with pytest.raises(CypherSyntaxError):
        run_untrusted(graph, "MATCH (d:Driver RETURN d")
