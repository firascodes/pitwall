"""POST /ask: run the agent and stream its steps and answer blocks as Server-Sent Events."""

import json
import logging
import uuid
from collections.abc import AsyncIterator, Iterator
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from langchain_core.messages import HumanMessage, ToolMessage
from pydantic import BaseModel, Field

from pitwall.agent.cost import CostMeter
from pitwall.api.auth import Asker, asker
from pitwall.api.limits import DailyBudget, client_ip
from pitwall.config import get_settings

log = logging.getLogger(__name__)
router = APIRouter()
PREVIEW_CHARS = 300


class Ask(BaseModel):
    question: str = Field(min_length=1, max_length=500)
    thread_id: str | None = None


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def step_events(node: str, update: dict[str, Any]) -> Iterator[tuple[str, Any]]:
    """One graph step -> the events the client shows in the agent trace and the answer."""
    if node == "planner":
        calls = update["messages"][-1].tool_calls
        yield (
            "step",
            {
                "node": node,
                "tool_calls": [
                    {"id": c["id"], "name": c["name"], "args": c["args"]} for c in calls
                ],
            },
        )
    elif node == "tools":
        for m in update["messages"]:
            if isinstance(m, ToolMessage):
                yield (
                    "tool",
                    {
                        "id": m.tool_call_id,
                        "name": m.name,
                        "ok": m.status != "error",
                        "preview": m.content[:PREVIEW_CHARS],
                        "queries": (m.artifact or {}).get("queries", []),
                    },
                )
    elif node == "composer":
        for block in update["blocks"]:
            yield "block", block


async def run(
    agent: Any,
    question: str,
    thread_id: str,
    meter: CostMeter,
    budget: DailyBudget | None = None,
    owner: str = "",
) -> AsyncIterator[tuple[str, Any]]:
    """One agent run as (event, data) pairs: the web streams them, the bot collects them.

    The checkpoint thread is namespaced by its owner, so a guessed thread_id reads nothing.
    """
    yield "start", {"thread_id": thread_id}
    thread = f"{owner}:{thread_id}" if owner else thread_id
    config = {"configurable": {"thread_id": thread}, "callbacks": [meter]}
    try:
        updates = agent.astream(
            {"messages": [HumanMessage(question)]}, config, stream_mode="updates"
        )
        async for update in updates:
            for node, change in update.items():
                for event in step_events(node, change):
                    yield event
    except Exception:
        log.exception("agent run failed for thread %s", thread_id)
        yield "error", {"message": "The agent failed on this question. Try again."}
    usage = meter.report()
    if budget is not None:
        await budget.add(usage["usd"])
    log.info("thread %s cost $%.6f over %d LLM calls", thread_id, usage["usd"], usage["llm_calls"])
    yield "done", {"usage": usage}


async def stream(*args: Any) -> AsyncIterator[str]:
    async for event, data in run(*args):
        yield sse(event, data)


def new_meter() -> CostMeter:
    s = get_settings()
    return CostMeter(s.llm_input_usd_per_mtok, s.llm_output_usd_per_mtok)


@router.post("/ask")
async def ask(body: Ask, request: Request) -> StreamingResponse:
    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        raise HTTPException(503, "The agent is not configured (PITWALL_OPENAI_API_KEY).")
    budget: DailyBudget = request.app.state.budget
    if budget.exhausted():
        raise HTTPException(429, "The demo spent today's LLM budget. It resets at 00:00 UTC.")
    if not request.app.state.limiter.allow(client_ip(request)):
        raise HTTPException(429, "Too many questions. Wait a minute and try again.")
    who = asker(request)
    s = get_settings()
    if s.supabase_url and not await request.app.state.quota.take(who.key, limit(who)):
        code = "user_limit" if who.signed_in else "guest_limit"
        message = (
            "That's all your questions for today. Back after 00:00 UTC."
            if who.signed_in
            else "That was your free question. Sign in to keep asking."
        )
        raise HTTPException(429, {"code": code, "message": message})
    thread_id = body.thread_id or uuid.uuid4().hex
    return StreamingResponse(
        stream(agent, body.question, thread_id, new_meter(), budget, who.key),
        media_type="text/event-stream",
    )


def limit(who: Asker) -> int:
    s = get_settings()
    return s.user_daily_questions if who.signed_in else s.guest_daily_questions


@router.get("/quota")
async def quota(request: Request) -> dict[str, Any]:
    """How many questions this asker has left today; the web shows it in the sidebar."""
    who = asker(request)
    used = await request.app.state.quota.used(who.key)
    return {
        "auth": bool(get_settings().supabase_url),
        "signed_in": who.signed_in,
        "used": used,
        "limit": limit(who),
    }


@router.get("/usage")
def usage(request: Request) -> dict[str, float | str]:
    """Today's LLM spend against the daily cap of the public demo."""
    return request.app.state.budget.report()
