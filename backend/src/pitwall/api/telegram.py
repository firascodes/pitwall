"""POST /telegram/webhook: Telegram pushes updates here; the secret header proves it is Telegram."""

import hmac

from fastapi import APIRouter, Header, HTTPException, Request

from pitwall.config import get_settings

router = APIRouter()


@router.post("/telegram/webhook")
async def webhook(
    request: Request, x_telegram_bot_api_secret_token: str | None = Header(default=None)
) -> dict[str, bool]:
    bot = getattr(request.app.state, "bot", None)
    secret = get_settings().telegram_webhook_secret
    if bot is None or secret is None:
        raise HTTPException(404, "The Telegram bot is not configured.")
    if not hmac.compare_digest(x_telegram_bot_api_secret_token or "", secret.get_secret_value()):
        raise HTTPException(403, "Bad webhook secret.")
    bot.schedule(await request.json())
    return {"ok": True}
