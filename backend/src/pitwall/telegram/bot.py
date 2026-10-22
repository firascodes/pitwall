"""The Telegram channel: an adapter from Telegram updates to the same agent run the web uses."""

import asyncio
import logging
from typing import Any

from pitwall.api.ask import new_meter, run
from pitwall.api.limits import DailyBudget, RateLimiter
from pitwall.telegram.client import TelegramClient
from pitwall.telegram.render import render

log = logging.getLogger(__name__)

WELCOME = (
    "<b>Pitwall</b> here, your race engineer for the 2026 season.\n\n"
    "Ask about results, teammates or any lap. Answers come from a Neo4j knowledge graph and "
    "real telemetry. /new starts a fresh conversation."
)
EXAMPLES = [
    "Compare Hamilton and Leclerc's fastest laps in Singapore qualifying",
    "Who leads the championship?",
    "How has Antonelli done against Russell?",
]


class Bot:
    def __init__(
        self,
        client: TelegramClient,
        agent: Any,
        web_url: str,
        budget: DailyBudget,
        limiter: RateLimiter,
    ) -> None:
        self.client, self.agent, self.web_url = client, agent, web_url
        self.budget, self.limiter = budget, limiter
        self.chips: dict[int, list[str]] = {}  # the last answer's follow-ups, per chat
        self.resets: dict[int, int] = {}  # /new bumps this to start a new agent thread
        self.tasks: set[asyncio.Task] = set()

    def schedule(self, update: dict) -> None:
        """Answer in the background: Telegram resends an update when the webhook is slow."""
        task = asyncio.create_task(self.handle(update))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def handle(self, update: dict) -> None:
        try:
            if query := update.get("callback_query"):
                await self.client.call("answerCallbackQuery", callback_query_id=query["id"])
                chat = query["message"]["chat"]["id"]
                index = int(query.get("data", "chip:-1").split(":")[1])
                options = self.chips.get(chat, [])
                if 0 <= index < len(options):
                    await self.answer(chat, query["from"]["id"], options[index])
            elif (message := update.get("message")) and (text := message.get("text")):
                await self.on_text(message["chat"]["id"], message["from"]["id"], text.strip())
        except Exception:
            log.exception("telegram update %s failed", update.get("update_id"))

    async def on_text(self, chat: int, user: int, text: str) -> None:
        if text.startswith("/start"):
            self.chips[chat] = EXAMPLES
            keyboard = [[{"text": q, "callback_data": f"chip:{i}"}] for i, q in enumerate(EXAMPLES)]
            await self.client.send(chat, WELCOME, keyboard)
        elif text.startswith("/new"):
            self.resets[chat] = self.resets.get(chat, 0) + 1
            await self.client.send(chat, "Fresh radio channel. What do you need?")
        else:
            await self.answer(chat, user, text[:500])

    async def answer(self, chat: int, user: int, question: str) -> None:
        if self.budget.exhausted():
            await self.client.send(chat, "Today's demo budget is spent. Back after 00:00 UTC.")
            return
        if not self.limiter.allow(f"tg-{user}"):
            await self.client.send(chat, "Box, box: too many questions. Try again in a minute.")
            return
        await self.client.typing(chat)
        thread = f"tg-{chat}-{self.resets.get(chat, 0)}"
        blocks: list[dict] = []
        usage = None
        async for event, data in run(self.agent, question, thread, new_meter(), self.budget):
            if event == "block":
                blocks.append(data)
            elif event == "tool":
                await self.client.typing(chat)
            elif event == "error":
                blocks.append({"type": "text", "text": data["message"]})
            elif event == "done":
                usage = data["usage"]
        text, keyboard, self.chips[chat] = render(blocks, usage, self.web_url)
        await self.client.send(chat, text, keyboard)
