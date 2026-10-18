import pytest
from neo4j import Driver, GraphDatabase
from neo4j.exceptions import ServiceUnavailable

from pitwall.config import get_settings


@pytest.fixture(scope="session")
def graph() -> Driver:
    """The local Neo4j with the 2026 season loaded; tests skip when it is not running."""
    s = get_settings()
    driver = GraphDatabase.driver(
        s.neo4j_uri,
        auth=(s.neo4j_user, s.neo4j_password.get_secret_value()),
        notifications_min_severity="OFF",
    )
    try:
        driver.verify_connectivity()
    except ServiceUnavailable:
        pytest.skip("Neo4j is not running (docker compose up -d)")
    yield driver
    driver.close()
