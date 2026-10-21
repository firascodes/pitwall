"""Read-only access to the graph: trusted templates and guarded LLM-written Cypher."""

import re
import time
from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any

from neo4j import READ_ACCESS, Driver, ManagedTransaction, unit_of_work
from neo4j.graph import Node, Path, Relationship
from neo4j.time import Date, DateTime

MAX_ROWS = 200
TIMEOUT_S = 5.0

# These count as reads in EXPLAIN but can reach files, URLs or admin procedures
DENYLIST = re.compile(r"\bLOAD\s+CSV\b|\bCALL\s+\w|\bapoc\.|\bPROFILE\b|\bEXPLAIN\b", re.I)


class UnsafeCypher(ValueError):
    pass


_log: ContextVar[list[dict[str, Any]] | None] = ContextVar("cypher_log", default=None)


@contextmanager
def recording() -> Iterator[list[dict[str, Any]]]:
    """Collect every query run in this context, for the agent trace."""
    token = _log.set([])
    try:
        yield _log.get()
    finally:
        _log.reset(token)


def _record(cypher: str, params: dict[str, Any], rows: int, started: float) -> None:
    if (log := _log.get()) is not None:
        ms = round((time.perf_counter() - started) * 1000, 1)
        log.append({"cypher": cypher.strip(), "params": params, "rows": rows, "ms": ms})


def plain(value: Any) -> Any:
    """Neo4j values -> JSON-safe Python values."""
    if isinstance(value, Node):
        return dict(value)
    if isinstance(value, Relationship):
        return {"type": value.type, **dict(value)}
    if isinstance(value, Path):
        return [plain(n) for n in value.nodes]
    if isinstance(value, Date | DateTime):
        return value.iso_format()
    if isinstance(value, float):
        return round(value, 4)
    if isinstance(value, list):
        return [plain(v) for v in value]
    if isinstance(value, dict):
        return {k: plain(v) for k, v in value.items()}
    return value


@unit_of_work(timeout=TIMEOUT_S)
def _fetch(tx: ManagedTransaction, cypher: str, params: dict[str, Any]) -> list[dict[str, Any]]:
    return [plain(r.data()) for r in tx.run(cypher, params).fetch(MAX_ROWS)]


def read_rows(driver: Driver, cypher: str, **params: Any) -> list[dict[str, Any]]:
    """Run a query in a read transaction: the server rejects any write."""
    started = time.perf_counter()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        rows = session.execute_read(_fetch, cypher, params)
    _record(cypher, params, len(rows), started)
    return rows


def run_untrusted(driver: Driver, cypher: str) -> list[dict[str, Any]]:
    """Defence in depth for LLM-written Cypher: denylist, EXPLAIN check, read transaction."""
    if DENYLIST.search(cypher):
        raise UnsafeCypher("procedure calls, file loads and PROFILE/EXPLAIN are not allowed")
    with driver.session(default_access_mode=READ_ACCESS) as session:
        query_type = session.run(f"EXPLAIN {cypher}").consume().query_type
        if query_type != "r":
            raise UnsafeCypher(f"only read queries are allowed, this one is '{query_type}'")
        started = time.perf_counter()
        rows = session.execute_read(_fetch, cypher, {})
    _record(cypher, {}, len(rows), started)
    return rows
