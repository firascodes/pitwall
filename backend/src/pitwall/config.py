from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """App settings, read from environment variables (or a local .env file)."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PITWALL_", extra="ignore")

    season: int = 2026
    neo4j_uri: str = "bolt://localhost:7687"
    neo4j_user: str = "neo4j"
    neo4j_password: SecretStr = SecretStr("pitwall-dev-password")
    database_url: str = "postgresql://pitwall:pitwall@localhost:5432/pitwall"
    data_dir: Path = Path("data")

    @property
    def fastf1_cache_dir(self) -> Path:
        return self.data_dir / "fastf1_cache"

    @property
    def telemetry_dir(self) -> Path:
        return self.data_dir / "telemetry"


@lru_cache
def get_settings() -> Settings:
    return Settings()
