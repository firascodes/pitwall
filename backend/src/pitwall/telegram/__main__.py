"""Run the bot locally with long polling, no public URL needed: python -m pitwall.telegram"""

import asyncio
import logging

from pitwall.api.main import app, lifespan


async def main() -> None:
    async with lifespan(app):
        bot = app.state.bot
        if bot is None:
            raise SystemExit("set PITWALL_TELEGRAM_BOT_TOKEN and PITWALL_OPENAI_API_KEY first")
        await bot.client.call("deleteWebhook")
        logging.info("polling Telegram; press Ctrl+C to stop")
        offset = 0
        while True:
            updates = await bot.client.call("getUpdates", offset=offset, timeout=50)
            for update in updates:
                offset = update["update_id"] + 1
                bot.schedule(update)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
