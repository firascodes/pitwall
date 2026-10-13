# Pit Wall

An F1 analysis agent built on a knowledge graph. Ask about the 2026 season in plain English and get answers backed by the data, plus pixel-art replays of real qualifying and race laps.

> 🚧 Work in progress. Unofficial fan project, not affiliated with Formula 1, the FIA or any team.

## What it will do

- **Answer questions with a knowledge graph.** "Who has beaten their teammate most often in qualifying this year?" goes to Neo4j through a LangGraph agent, and every answer cites the rows it came from.
- **Replay laps.** "Show me Lewis's last Q3 lap against pole" rebuilds both laps from real telemetry as a retro pixel-art replay, with a ghost car and a corner-by-corner time delta.
- **Run on Telegram too.** Ask the bot and open replays in a Telegram Mini App.

## Stack

Python (FastAPI, LangGraph, FastF1, Polars) · Neo4j · Parquet · Postgres · Next.js + PixiJS · Telegram

## Docs

- [Architecture plan](docs/architecture.md): system design, graph model, decisions and deliverables

## Data

Results from [Jolpica-F1](https://github.com/jolpica/jolpica-f1), timing and telemetry via [FastF1](https://github.com/theOehrly/Fast-F1), session data from [OpenF1](https://openf1.org).

## License

MIT
