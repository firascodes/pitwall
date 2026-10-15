# Pit Wall backend

Python service: ingest, knowledge graph, agent and API.

```bash
uv sync                                        # install deps into .venv
uv run uvicorn pitwall.api.main:app --reload   # http://localhost:8000/docs
uv run pytest                                  # tests
uv run ruff check . && uv run ruff format .    # lint + format
```
