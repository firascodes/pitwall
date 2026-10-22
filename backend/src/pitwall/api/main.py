import logging
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

from pitwall import __version__
from pitwall.api import ask, laps, telegram
from pitwall.api.limits import DailyBudget, DailyQuota, RateLimiter
from pitwall.config import Settings, get_settings
from pitwall.graph.db import connect
from pitwall.telemetry.locks import postgres_lock
from pitwall.telemetry.source import openf1_lap_loader
from pitwall.telemetry.store import TelemetryStore

log = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Open shared clients once per process; the agent starts only when an LLM key is set."""
    s = get_settings()
    app.state.budget = DailyBudget(s.daily_usd_cap, s.database_url)
    await app.state.budget.load()
    app.state.quota = DailyQuota(s.database_url)
    await app.state.quota.setup()
    async with AsyncExitStack() as stack:
        graph = connect(s)
        stack.callback(graph.close)
        app.state.store = TelemetryStore(
            s.telemetry_dir, openf1_lap_loader(graph), postgres_lock(s.database_url)
        )
        app.state.agent = None
        if s.openai_api_key:
            from pitwall.agent.factory import create_agent

            pool = AsyncConnectionPool(
                s.database_url,
                kwargs={"autocommit": True, "prepare_threshold": 0, "row_factory": dict_row},
                open=False,
            )
            await stack.enter_async_context(pool)
            checkpointer = AsyncPostgresSaver(pool)
            await checkpointer.setup()
            app.state.agent = create_agent(s, graph, app.state.store, checkpointer)
        else:
            log.warning("PITWALL_OPENAI_API_KEY is not set: /ask is disabled")
        app.state.bot = None
        if app.state.agent is not None and s.telegram_bot_token:
            await start_bot(app, s, stack)
        yield


async def start_bot(app: FastAPI, s: Settings, stack: AsyncExitStack) -> None:
    """Telegram channel: register the webhook (and the Mini App menu button) when public."""
    from pitwall.telegram.bot import Bot
    from pitwall.telegram.client import TelegramClient

    client = TelegramClient(s.telegram_bot_token.get_secret_value())
    stack.push_async_callback(client.close)
    app.state.bot = Bot(client, app.state.agent, s.web_url, app.state.budget, app.state.limiter)
    if s.telegram_webhook_secret and s.api_url.startswith("https://"):
        await client.call(
            "setWebhook",
            url=f"{s.api_url.rstrip('/')}/telegram/webhook",
            secret_token=s.telegram_webhook_secret.get_secret_value(),
            allowed_updates=["message", "callback_query"],
        )
        await client.call(
            "setChatMenuButton",
            menu_button={"type": "web_app", "text": "Pitwall", "web_app": {"url": s.web_url}},
        )
        log.info("telegram webhook set to %s", s.api_url)


app = FastAPI(title="Pit Wall API", version=__version__, lifespan=lifespan)
app.state.budget = DailyBudget(get_settings().daily_usd_cap)
app.state.limiter = RateLimiter(get_settings().ask_per_minute)
app.state.quota = DailyQuota()
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["content-type", "authorization"],
)
app.include_router(ask.router)
app.include_router(laps.router)
app.include_router(telegram.router)


@app.get("/health")
def health() -> dict[str, str | int | bool]:
    """Liveness check: the process is up and can answer requests."""
    return {
        "status": "ok",
        "version": __version__,
        "season": get_settings().season,
        "agent": getattr(app.state, "agent", None) is not None,
        "auth": bool(get_settings().supabase_url),
    }
