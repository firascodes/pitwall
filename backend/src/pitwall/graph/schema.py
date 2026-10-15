"""Graph constraints and indexes. Safe to run many times (IF NOT EXISTS)."""

from neo4j import Driver

# A uniqueness constraint also creates an index, so MERGE on these keys is a lookup, not a scan.
UNIQUE_KEYS = {
    "Driver": "driver_id",
    "Constructor": "constructor_id",
    "Circuit": "circuit_id",
    "Race": "race_id",
    "Session": "session_id",
    "Result": "result_id",
    "Stint": "stint_id",
    "Lap": "lap_id",
}

# Extra indexes for frequent filters
INDEXES = {
    "race_season": ("Race", "season"),
    "session_type": ("Session", "type"),
    "stint_season": ("Stint", "season"),
}


def apply_schema(driver: Driver) -> None:
    for label, key in UNIQUE_KEYS.items():
        driver.execute_query(
            f"CREATE CONSTRAINT {label.lower()}_{key} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{key} IS UNIQUE"
        )
    for name, (label, prop) in INDEXES.items():
        driver.execute_query(f"CREATE INDEX {name} IF NOT EXISTS FOR (n:{label}) ON (n.{prop})")
    driver.execute_query("CALL db.awaitIndexes(60)")
