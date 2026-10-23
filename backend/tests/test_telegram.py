from fastapi.testclient import TestClient
from langchain_core.messages import AIMessage
from pydantic import SecretStr

from pitwall.api.limits import DailyBudget, RateLimiter
from pitwall.api.main import app
from pitwall.config import get_settings
from pitwall.telegram.bot import Bot
from pitwall.telegram.render import render, text_html

REPLAY = {
    "type": "lap_replay",
    "title": "Replay",
    "source": "r1",
    "data": {
        "laps": ["2026-17-Q-hamilton-21", "2026-17-Q-leclerc-24"],
        "drivers": ["Lewis Hamilton", "Charles Leclerc"],
        "times": ["1:31.496", "1:31.427"],
        "ghost": True,
    },
}


def test_markdown_becomes_telegram_html_without_citations() -> None:
    assert text_html("**Leclerc** won <easily> [r1, r2]\n- T16") == (
        "<b>Leclerc</b> won &lt;easily&gt;\n• T16"
    )


def test_replays_open_the_mini_app_and_chips_become_buttons() -> None:
    blocks = [
        {"type": "text", "text": "Leclerc was faster [r1]."},
        REPLAY,
        {"type": "chips", "options": ["Who took pole?"]},
    ]
    text, keyboard, chips = render(blocks, {"usd": 0.000776, "llm_calls": 4}, "https://pitwall.app")
    assert text == "Leclerc was faster.\n\n<i>$0.000776 · 4 LLM calls</i>"
    url = keyboard[0][0]["web_app"]["url"]
    assert url.startswith("https://pitwall.app/replay?laps=2026-17-Q-hamilton-21%2C2026-17-Q")
    assert keyboard[1] == [{"text": "Who took pole?", "callback_data": "chip:0"}]
    assert chips == ["Who took pole?"]


def test_no_mini_app_button_without_https() -> None:
    _, keyboard, _ = render([REPLAY], None, "http://localhost:3000")
    assert keyboard == []


def test_tables_fall_back_to_text() -> None:
    rows = [{"pos": i, "driver": f"Driver {i}"} for i in range(1, 13)]
    text, _, _ = render([{"type": "results_table", "data": {"rows": rows}}], None, "")
    assert text.startswith("<pre>1 Driver 1\n") and "… 2 more rows" in text


class FakeClient:
    def __init__(self) -> None:
        self.sent: list[tuple[int, str, list | None]] = []

    async def send(self, chat_id, text, keyboard=None):
        self.sent.append((chat_id, text, keyboard))

    async def typing(self, chat_id):
        pass

    async def call(self, method, **params):
        pass


class FakeAgent:
    async def astream(self, state, config, stream_mode):
        assert config["configurable"]["thread_id"] == "tg-7-0"
        yield "updates", {"planner": {"messages": [AIMessage("Russell leads.")]}}
        yield (
            "updates",
            {"composer": {"blocks": [{"type": "text", "text": "**Russell** leads [r1]."}]}},
        )


def bot(client: FakeClient) -> Bot:
    return Bot(client, FakeAgent(), "https://pitwall.app", DailyBudget(1.0), RateLimiter(5))


async def test_a_message_gets_the_agent_answer() -> None:
    client = FakeClient()
    await bot(client).handle({"message": {"chat": {"id": 7}, "from": {"id": 1}, "text": "Leader?"}})
    assert client.sent == [(7, "<b>Russell</b> leads.\n\n<i>$0.000000 · 0 LLM calls</i>", [])]


async def test_start_offers_example_questions() -> None:
    client = FakeClient()
    await bot(client).handle({"message": {"chat": {"id": 7}, "from": {"id": 1}, "text": "/start"}})
    assert len(client.sent[0][2]) == 3


def test_webhook_rejects_a_wrong_secret() -> None:
    settings = get_settings()
    settings.telegram_webhook_secret = SecretStr("s3cret")
    app.state.bot = bot(FakeClient())
    try:
        client = TestClient(app)
        bad = client.post(
            "/telegram/webhook", json={}, headers={"x-telegram-bot-api-secret-token": "no"}
        )
        assert bad.status_code == 403
        ok = client.post(
            "/telegram/webhook",
            json={"update_id": 1},
            headers={"x-telegram-bot-api-secret-token": "s3cret"},
        )
        assert ok.json() == {"ok": True}
    finally:
        settings.telegram_webhook_secret = None
        app.state.bot = None
