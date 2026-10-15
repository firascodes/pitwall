from fastapi import FastAPI

from pitwall import __version__
from pitwall.config import get_settings

app = FastAPI(title="Pit Wall API", version=__version__)


@app.get("/health")
def health() -> dict[str, str | int]:
    """Liveness check: the process is up and can answer requests."""
    return {"status": "ok", "version": __version__, "season": get_settings().season}
