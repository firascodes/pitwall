from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from langchain_core.runnables import RunnableLambda
from langchain_core.tools import tool
from langgraph.checkpoint.memory import InMemorySaver

from pitwall.agent.answer import ComponentDraft, Draft, TextDraft
from pitwall.agent.graph import build_agent


class Scripted(BaseChatModel):
    """A fake model: returns scripted replies and records whether tools could be called."""

    replies: list[AIMessage]
    draft: Draft
    log: list[str]
    tool_choice: str | None = None

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, tool_choice=None, **_):
        return self.model_copy(update={"tool_choice": tool_choice or "auto"})

    def with_structured_output(self, schema, **_):
        return RunnableLambda(lambda messages: self.log.append(messages[-1].content) or self.draft)

    def _generate(self, messages, stop=None, run_manager=None, **_) -> ChatResult:
        self.log.append(f"planner tool_choice={self.tool_choice}")
        return ChatResult(generations=[ChatGeneration(message=self.replies.pop(0))])


@tool(response_format="content_and_artifact")
def standings(by: str = "driver"):
    """Championship standings."""
    rows = [{"name": "George Russell", "points": 301}]
    return '[{"name": "George Russell", "points": 301}]', {"kind": "rows", "data": rows}


@tool
def broken() -> str:
    """Always fails."""
    raise LookupError("no driver matches 'Senna'")


def call(name: str, i: int, **args: Any) -> AIMessage:
    return AIMessage("", tool_calls=[{"name": name, "args": args, "id": f"c{i}"}])


def agent(replies, draft, **kw):
    model = Scripted(replies=replies, draft=draft, log=[])  # pydantic copies lists: read model.log
    return build_agent(model, [standings, broken], season=2026, last_round=17, **kw), model.log


DRAFT = Draft(
    blocks=[
        TextDraft(type="text", text="Russell leads with 301 points [r1]."),
        ComponentDraft(type="component", component="results_table", source="r1", title="Standings"),
    ]
)


async def test_tool_results_flow_into_hydrated_components() -> None:
    graph, log = agent([call("standings", 1), AIMessage("Russell leads on 301.")], DRAFT)
    out = await graph.ainvoke({"messages": [HumanMessage("Who leads?")]})
    assert [b["type"] for b in out["blocks"]] == ["text", "results_table"]
    assert out["blocks"][1]["data"]["rows"][0]["points"] == 301
    assert "[r1] standings -> can fill: results_table" in log[-1]


async def test_tool_errors_return_to_the_planner_and_are_not_sources() -> None:
    graph, log = agent([call("broken", 1), AIMessage("Which driver did you mean?")], DRAFT)
    out = await graph.ainvoke({"messages": [HumanMessage("How fast was Senna?")]})
    error = next(m for m in out["messages"] if isinstance(m, ToolMessage))
    assert error.status == "error" and "Senna" in error.content
    assert [b["type"] for b in out["blocks"]] == ["text"]  # the r1 component had no source


async def test_tool_budget_unbinds_tools() -> None:
    replies = [call("standings", 1), call("standings", 2), AIMessage("done")]
    graph, log = agent(replies, DRAFT, max_tool_calls=2)
    await graph.ainvoke({"messages": [HumanMessage("Loop forever")]})
    planner_calls = [line for line in log if line.startswith("planner")]
    assert planner_calls[-1] == "planner tool_choice=none"


async def test_memory_keeps_history_but_sources_are_per_turn() -> None:
    replies = [call("standings", 1), AIMessage("Russell."), AIMessage("He has 301.")]
    graph, log = agent(replies, DRAFT, checkpointer=InMemorySaver())
    config = {"configurable": {"thread_id": "t1"}}
    await graph.ainvoke({"messages": [HumanMessage("Who leads?")]}, config)
    out = await graph.ainvoke({"messages": [HumanMessage("How many points?")]}, config)
    assert len([m for m in out["messages"] if isinstance(m, HumanMessage)]) == 2
    assert "Sources:\nnone" in log[-1]
