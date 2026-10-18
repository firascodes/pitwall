"""The Pit Wall agent as a LangGraph state graph: planner <-> tools, then composer."""

from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AnyMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.prebuilt import ToolNode

from pitwall.agent.answer import Draft, Source, catalog, hydrate
from pitwall.agent.prompts import COMPOSER, planner_prompt

HISTORY_TURNS = 4


class AgentState(MessagesState):
    blocks: list[dict[str, Any]]


def current_turn(messages: list[AnyMessage]) -> list[AnyMessage]:
    last_human = max(i for i, m in enumerate(messages) if isinstance(m, HumanMessage))
    return messages[last_human:]


def recent(messages: list[AnyMessage], turns: int = HISTORY_TURNS) -> list[AnyMessage]:
    humans = [i for i, m in enumerate(messages) if isinstance(m, HumanMessage)]
    return messages[humans[-turns] if len(humans) > turns else 0 :]


def sources(turn: list[AnyMessage]) -> dict[str, Source]:
    results = [m for m in turn if isinstance(m, ToolMessage) and m.artifact and m.status != "error"]
    return {
        f"r{i}": Source(f"r{i}", m.name, m.artifact["kind"], m.artifact["data"], m.content)
        for i, m in enumerate(results, start=1)
    }


def build_agent(
    model: BaseChatModel,
    tools: list[BaseTool],
    *,
    season: int,
    last_round: int,
    max_tool_calls: int = 6,
    checkpointer: BaseCheckpointSaver | None = None,
) -> CompiledStateGraph:
    planner_llm = model.bind_tools(tools)
    wrap_up_llm = model.bind_tools(tools, tool_choice="none")  # budget spent: tools can't be called
    composer_llm = model.with_structured_output(Draft, method="json_schema", strict=True)
    system = SystemMessage(planner_prompt(season, last_round))

    async def planner(state: AgentState) -> dict:
        used = sum(isinstance(m, ToolMessage) for m in current_turn(state["messages"]))
        llm = planner_llm if used < max_tool_calls else wrap_up_llm
        reply = await llm.ainvoke([system, *recent(state["messages"])])
        return {"messages": [reply]}

    def after_planner(state: AgentState) -> str:
        return "tools" if state["messages"][-1].tool_calls else "composer"

    async def composer(state: AgentState) -> dict:
        turn = current_turn(state["messages"])
        found = sources(turn)
        brief = (
            f"Question: {turn[0].content}\n\nFindings:\n{turn[-1].content}\n\n"
            f"Sources:\n{catalog(found) or 'none'}"
        )
        draft = await composer_llm.ainvoke([SystemMessage(COMPOSER), HumanMessage(brief)])
        return {"blocks": hydrate(draft, found)}

    graph = StateGraph(AgentState)
    graph.add_node("planner", planner)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_node("composer", composer)
    graph.add_edge(START, "planner")
    graph.add_conditional_edges("planner", after_planner, ["tools", "composer"])
    graph.add_edge("tools", "planner")
    graph.add_edge("composer", END)
    return graph.compile(checkpointer=checkpointer)
