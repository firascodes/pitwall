"""A thin async client for the Telegram Bot API methods the bot uses."""

from typing import Any

import httpx


class TelegramError(RuntimeError):
    pass


class TelegramClient:
    def __init__(self, token: str, timeout_s: float = 60) -> None:
        self.http = httpx.AsyncClient(
            base_url=f"https://api.telegram.org/bot{token}/", timeout=timeout_s
        )

    async def call(self, method: str, **params: Any) -> Any:
        body = (await self.http.post(method, json=params)).json()
        if not body.get("ok"):
            raise TelegramError(f"{method}: {body.get('description')}")
        return body["result"]

    async def send(self, chat_id: int, text: str, keyboard: list | None = None) -> None:
        markup = {"reply_markup": {"inline_keyboard": keyboard}} if keyboard else {}
        await self.call(
            "sendMessage",
            chat_id=chat_id,
            text=text,
            parse_mode="HTML",
            link_preview_options={"is_disabled": True},
            **markup,
        )

    async def typing(self, chat_id: int) -> None:
        await self.call("sendChatAction", chat_id=chat_id, action="typing")

    async def close(self) -> None:
        await self.http.aclose()
