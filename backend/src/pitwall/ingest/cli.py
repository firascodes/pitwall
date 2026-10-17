import argparse
import logging

from pitwall.config import get_settings
from pitwall.graph.db import connect
from pitwall.ingest.laps_pipeline import run_laps_ingest
from pitwall.ingest.pipeline import run_ingest


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("neo4j.notifications").setLevel(logging.WARNING)


def main(argv: list[str] | None = None) -> None:
    """pitwall-ingest: results, sessions and derived data from Jolpica."""
    parser = argparse.ArgumentParser(description="Load an F1 season into the Neo4j graph.")
    parser.add_argument("--season", type=int, default=get_settings().season)
    args = parser.parse_args(argv)
    _setup_logging()
    with connect() as driver:
        print(run_ingest(args.season, driver))


def laps_main(argv: list[str] | None = None) -> None:
    """pitwall-ingest-laps: Lap nodes for every session + hot-set telemetry to Parquet."""
    parser = argparse.ArgumentParser(description="Load laps and hot-set telemetry.")
    parser.add_argument("--season", type=int, default=get_settings().season)
    parser.add_argument("--round", type=int, default=None, help="only this round")
    args = parser.parse_args(argv)
    _setup_logging()
    with connect() as driver:
        metrics = run_laps_ingest(driver, get_settings().telemetry_dir, args.season, args.round)
    for m in metrics:
        print(m)


if __name__ == "__main__":
    main()
