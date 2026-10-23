import json

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, AIMessageChunk, ToolMessage

from pitwall.api.ask import AnswerText
from pitwall.api.limits import DailyBudget, RateLimiter
from pitwall.api.main import app


class FakeAgent:
    async def astream(self, state, config, stream_mode):
        call = {"name": "standings", "args": {}, "id": "c1"}
        yield "updates", {"planner": {"messages": [AIMessage("", tool_calls=[call])]}}
        yield (
            "updates",
            {"tools": {"messages": [ToolMessage("[...]", tool_call_id="c1", name="standings")]}},
        )
        yield "updates", {"planner": {"messages": [AIMessage("Russell leads.")]}}
        for token in ('{"blocks": [{"type": "text", "text": "Russ', 'ell leads [r1]."}', "]}"):
            yield "messages", (AIMessageChunk(token), {"langgraph_node": "composer"})
        yield "updates", {"composer": {"blocks": [{"type": "text", "text": "Russell leads [r1]."}]}}


def events(body: str) -> list[tuple[str, dict]]:
    parsed = []
    for chunk in body.strip().split("\n\n"):
        event, data = chunk.split("\n")
        parsed.append((event.removeprefix("event: "), json.loads(data.removeprefix("data: "))))
    return parsed


def test_ask_streams_steps_then_blocks() -> None:
    app.state.agent = FakeAgent()
    response = TestClient(app).post("/ask", json={"question": "Who leads?", "thread_id": "t1"})
    assert response.headers["content-type"].startswith("text/event-stream")
    got = events(response.text)
    assert [e for e, _ in got] == [
        "start", "step", "tool", "step", "delta", "delta", "block", "done"
    ]  # fmt: skip
    assert "".join(d["text"] for e, d in got if e == "delta") == "Russell leads [r1]."
    assert got[0][1] == {"thread_id": "t1"}
    assert got[1][1]["tool_calls"] == [{"id": "c1", "name": "standings", "args": {}}]
    assert got[2][1]["id"] == "c1" and got[2][1]["queries"] == []
    assert got[6][1]["text"] == "Russell leads [r1]."
    assert got[7][1]["usage"]["usd"] == 0.0


async def test_ask_stops_when_the_daily_budget_is_spent() -> None:
    app.state.agent = FakeAgent()
    app.state.budget = DailyBudget(cap_usd=0.01)
    await app.state.budget.add(0.02)
    response = TestClient(app).post("/ask", json={"question": "Who leads?"})
    assert response.status_code == 429
    assert TestClient(app).get("/usage").json()["spent_usd"] == 0.02
    app.state.budget = DailyBudget(cap_usd=1.0)


def test_ask_without_an_llm_key_is_unavailable() -> None:
    app.state.agent = None
    assert TestClient(app).post("/ask", json={"question": "Hi"}).status_code == 503


def test_rate_limiter_blocks_after_the_limit() -> None:
    limiter = RateLimiter(limit=2)
    assert [limiter.allow("ip"), limiter.allow("ip"), limiter.allow("ip")] == [True, True, False]
    assert limiter.allow("other-ip")


def test_answer_text_survives_prefixes_that_are_not_json_yet() -> None:
    draft = AnswerText()
    tokens = ["", "{", '"blo', 'cks": [{"type": "text", "text": "Ant', 'onelli"}]}']
    assert "".join(draft.feed(AIMessageChunk(t)) for t in tokens) == "Antonelli"
