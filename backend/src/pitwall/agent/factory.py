"""Wire the agent from settings: model, tools, and the season facts the prompt needs."""

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph.state import CompiledStateGraph
from neo4j import Driver

from pitwall.agent.graph import build_agent
from pitwall.agent.tools.graph import graph_tools
from pitwall.agent.tools.laps import lap_tools
from pitwall.config import Settings
from pitwall.graph.query import read_rows
from pitwall.telemetry.store import TelemetryStore

LAST_ROUND = """
MATCH (r:Race {season: $season})-[:HAS_SESSION]->(:Session)<-[:IN_SESSION]-(:Result)
RETURN max(r.round) AS last_round
"""


def chat_model(settings: Settings) -> ChatOpenAI:
    if settings.openai_api_key is None:
        raise RuntimeError("set PITWALL_OPENAI_API_KEY to use the agent")
    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.openai_api_key,
        use_responses_api=True,
        reasoning={"effort": settings.llm_reasoning_effort},
        timeout=60,
        max_retries=2,
    )


def create_agent(
    settings: Settings, graph: Driver, store: TelemetryStore, checkpointer: BaseCheckpointSaver
) -> CompiledStateGraph:
    tools = graph_tools(graph, settings.season) + lap_tools(
        graph, store, settings.circuits_dir, settings.season
    )
    last_round = read_rows(graph, LAST_ROUND, season=settings.season)[0]["last_round"]
    return build_agent(
        chat_model(settings),
        tools,
        season=settings.season,
        last_round=last_round,
        max_tool_calls=settings.agent_max_tool_calls,
        checkpointer=checkpointer,
    )
