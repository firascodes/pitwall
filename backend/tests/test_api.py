import json

from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage, ToolMessage

from pitwall.api.limits import DailyBudget, RateLimiter
from pitwall.api.main import app


class FakeAgent:
    async def astream(self, state, config, stream_mode):
        call = {"name": "standings", "args": {}, "id": "c1"}
        yield {"planner": {"messages": [AIMessage("", tool_calls=[call])]}}
        yield {"tools": {"messages": [ToolMessage("[...]", tool_call_id="c1", name="standings")]}}
        yield {"planner": {"messages": [AIMessage("Russell leads.")]}}
        yield {"composer": {"blocks": [{"type": "text", "text": "Russell leads [r1]."}]}}


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
    assert [e for e, _ in got] == ["start", "step", "tool", "step", "block", "done"]
    assert got[0][1] == {"thread_id": "t1"}
    assert got[1][1]["tool_calls"] == [{"id": "c1", "name": "standings", "args": {}}]
    assert got[2][1]["id"] == "c1" and got[2][1]["queries"] == []
    assert got[4][1]["text"] == "Russell leads [r1]."
    assert got[5][1]["usage"]["usd"] == 0.0


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
