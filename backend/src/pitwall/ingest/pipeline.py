"""Load one season into the graph: schema -> races -> results -> derived data."""

import logging
import time

from neo4j import Driver

from pitwall.graph.schema import apply_schema
from pitwall.ingest.derive import rebuild_derived
from pitwall.ingest.load import RACES_CYPHER, RESULTS_CYPHER, write_rows
from pitwall.ingest.rows import race_rows, result_rows
from pitwall.sources.jolpica import RESULT_KEYS, JolpicaClient

SESSION_NAMES = {"results": "race", "qualifying": "qualifying", "sprint": "sprint"}

log = logging.getLogger(__name__)


def run_ingest(season: int, driver: Driver, jolpica: JolpicaClient | None = None) -> dict[str, int]:
    jolpica = jolpica or JolpicaClient()
    started = time.monotonic()
    summary: dict[str, int] = {}

    apply_schema(driver)

    # The schedule first: it creates every Race and Session that results attach to
    schedule = jolpica.fetch_races(season, "races")
    summary["races"] = write_rows(driver, RACES_CYPHER, race_rows(schedule))
    log.info("races: %s", summary["races"])

    for endpoint, key in RESULT_KEYS.items():
        rows = result_rows(endpoint, jolpica.fetch_races(season, endpoint), key)
        summary[f"{SESSION_NAMES[endpoint]}_results"] = write_rows(driver, RESULTS_CYPHER, rows)
        log.info("%s results: %s", endpoint, len(rows))

    summary |= rebuild_derived(driver, season)
    log.info("derived: %s", summary)
    log.info("ingest for %s finished in %.1fs", season, time.monotonic() - started)
    return summary
