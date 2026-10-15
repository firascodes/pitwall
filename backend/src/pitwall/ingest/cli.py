import argparse
import logging

from pitwall.config import get_settings
from pitwall.graph.db import connect
from pitwall.ingest.pipeline import run_ingest


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Load an F1 season into the Neo4j graph.")
    parser.add_argument("--season", type=int, default=get_settings().season)
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)

    with connect() as driver:
        summary = run_ingest(args.season, driver)
    print(summary)


if __name__ == "__main__":
    main()
