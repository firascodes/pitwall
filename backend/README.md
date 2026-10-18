# Pit Wall backend

Python service: ingest, knowledge graph, agent and API.

```bash
uv sync                                        # install deps into .venv
uv run pytest                                  # tests (graph tests skip if Neo4j is down)
uv run ruff check . && uv run ruff format .    # lint + format
```

## Run it

```bash
cd .. && docker compose up -d --wait           # Neo4j + Postgres
cd backend
uv run pitwall-ingest --season 2026            # results -> graph (approx. 1 min)
uv run pitwall-ingest-laps --season 2026       # laps + hot-set telemetry (approx. 70 min)
cp .env.example .env                           # then set PITWALL_OPENAI_API_KEY
uv run uvicorn pitwall.api.main:app --reload   # http://localhost:8000/docs
```

## Ask the agent

```bash
curl -N localhost:8000/ask -H 'content-type: application/json' \
  -d '{"question": "Compare Hamilton and Leclerc in Singapore Q3"}'
```

The response is a stream of Server-Sent Events: `start`, `step` (planner tool calls), `tool`
(results), `block` (answer blocks: text, components, chips) and `done`. Send the `thread_id`
from `start` with the next question to continue the conversation.
