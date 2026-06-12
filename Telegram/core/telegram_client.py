import os
from telethon import TelegramClient
from Telegram.config import API_ID, API_HASH, SESSION_NAME
import logging

log = logging.getLogger("BOT")

_client = None  # singleton instance


async def start_telegram():
    global _client

    if _client is not None:
        return _client  # already started

    try:
        log.info("Starting Telegram client...")

        client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
        await client.start()  # type: ignore[misc]  # Telethon stubs incorrectly type start() as non-awaitable

        me = await client.get_me()
        log.info(f"Telegram connected as {me.username or me.id}")

        _client = client
        return client

    except Exception as e:
        log.critical(f"Telegram startup failed: {e}")
        raise