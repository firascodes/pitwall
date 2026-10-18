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
    database_url: str = "postgresql://pitwall:pitwall@localhost:5433/pitwall"
    data_dir: Path = Path("data")
    openai_api_key: SecretStr | None = None
    llm_model: str = "gpt-6-luna"  # smallest current OpenAI model with tool calling
    llm_reasoning_effort: str = "low"
    agent_max_tool_calls: int = 6

    @property
    def fastf1_cache_dir(self) -> Path:
        return self.data_dir / "fastf1_cache"

    @property
    def telemetry_dir(self) -> Path:
        return self.data_dir / "telemetry"

    @property
    def circuits_dir(self) -> Path:
        return self.data_dir / "circuits"


@lru_cache
def get_settings() -> Settings:
    return Settings()
