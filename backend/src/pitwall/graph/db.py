from neo4j import Driver, GraphDatabase

from pitwall.config import Settings, get_settings


def connect(settings: Settings | None = None) -> Driver:
    """Open a Neo4j driver. The driver holds a connection pool: create one per process."""
    s = settings or get_settings()
    driver = GraphDatabase.driver(
        s.neo4j_uri, auth=(s.neo4j_user, s.neo4j_password.get_secret_value())
    )
    driver.verify_connectivity()
    return driver
