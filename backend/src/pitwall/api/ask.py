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
            {"node": node, "tool_calls": [{"name": c["name"], "args": c["args"]} for c in calls]},
        )
    elif node == "tools":
        for m in update["messages"]:
            if isinstance(m, ToolMessage):
                ok = m.status != "error"
                yield "tool", {"name": m.name, "ok": ok, "preview": m.content[:PREVIEW_CHARS]}
    elif node == "composer":
        for block in update["blocks"]:
            yield "block", block


async def stream(agent: Any, question: str, thread_id: str) -> AsyncIterator[str]:
    yield sse("start", {"thread_id": thread_id})
    config = {"configurable": {"thread_id": thread_id}}
    try:
        updates = agent.astream(
            {"messages": [HumanMessage(question)]}, config, stream_mode="updates"
        )
        async for update in updates:
            for node, change in update.items():
                for event, data in step_events(node, change):
                    yield sse(event, data)
    except Exception:
        log.exception("agent run failed for thread %s", thread_id)
        yield sse("error", {"message": "The agent failed on this question. Try again."})
    yield sse("done", {})


@router.post("/ask")
async def ask(body: Ask, request: Request) -> StreamingResponse:
    agent = getattr(request.app.state, "agent", None)
    if agent is None:
        raise HTTPException(503, "The agent is not configured (PITWALL_OPENAI_API_KEY).")
    thread_id = body.thread_id or uuid.uuid4().hex
    return StreamingResponse(
        stream(agent, body.question, thread_id), media_type="text/event-stream"
    )
