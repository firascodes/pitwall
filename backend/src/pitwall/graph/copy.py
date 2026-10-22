"""Copy the local graph to another Neo4j (for example AuraDB Free), instead of a 70-minute ingest.

PITWALL_TARGET_NEO4J_URI=neo4j+s://xxxx.databases.neo4j.io PITWALL_TARGET_NEO4J_PASSWORD=... \\
  uv run pitwall-copy-graph --replace
"""

import argparse
import os
from collections import defaultdict
from itertools import batched

from neo4j import Driver, GraphDatabase

from pitwall.graph.db import connect
from pitwall.graph.schema import UNIQUE_KEYS, apply_schema

BATCH = 1000

RELATIONSHIPS = """
MATCH (a)-[r]->(b)
RETURN head(labels(a)) AS la, a[$keys[head(labels(a))]] AS ka, type(r) AS type,
       properties(r) AS props, head(labels(b)) AS lb, b[$keys[head(labels(b))]] AS kb
"""


def copy_graph(source: Driver, target: Driver) -> dict[str, int]:
    """Nodes by their unique key, then relationships between those keys. Target must be empty."""
    apply_schema(target)
    counts: dict[str, int] = defaultdict(int)
    for label in UNIQUE_KEYS:
        nodes = [
            r["p"] for r in source.execute_query(f"MATCH (n:{label}) RETURN n {{.*}} AS p").records
        ]
        for chunk in batched(nodes, BATCH):
            target.execute_query(
                f"UNWIND $rows AS p CREATE (n:{label}) SET n = p", rows=list(chunk)
            )
        counts[label] = len(nodes)

    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for r in source.execute_query(RELATIONSHIPS, keys=UNIQUE_KEYS).records:
        groups[(r["la"], r["type"], r["lb"])].append({"a": r["ka"], "b": r["kb"], "p": r["props"]})
    for (la, rel, lb), rows in groups.items():
        ka, kb = UNIQUE_KEYS[la], UNIQUE_KEYS[lb]
        cypher = (
            f"UNWIND $rows AS r MATCH (a:{la} {{{ka}: r.a}}), (b:{lb} {{{kb}: r.b}}) "
            f"CREATE (a)-[x:{rel}]->(b) SET x = r.p"
        )
        for chunk in batched(rows, BATCH):
            target.execute_query(cypher, rows=list(chunk))
        counts[rel] += len(rows)
    return dict(counts)


def main() -> None:
    parser = argparse.ArgumentParser(prog="pitwall-copy-graph")
    parser.add_argument("--replace", action="store_true", help="delete everything in the target")
    args = parser.parse_args()
    uri = os.environ["PITWALL_TARGET_NEO4J_URI"]
    auth = (
        os.environ.get("PITWALL_TARGET_NEO4J_USER", "neo4j"),
        os.environ["PITWALL_TARGET_NEO4J_PASSWORD"],
    )
    source = connect()
    with GraphDatabase.driver(uri, auth=auth) as target:
        target.verify_connectivity()
        existing = target.execute_query("MATCH (n) RETURN count(n) AS n").records[0]["n"]
        if existing and not args.replace:
            raise SystemExit(
                f"the target has {existing} nodes: pass --replace to delete them first"
            )
        if existing:
            with target.session() as session:  # IN TRANSACTIONS needs an auto-commit query
                session.run("MATCH (n) CALL (n) { DETACH DELETE n } IN TRANSACTIONS OF 5000 ROWS")
        for name, n in copy_graph(source, target).items():
            print(f"{name:<14} {n:>7,}")
    source.close()
