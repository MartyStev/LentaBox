import sys

from telethon import TelegramClient

import config
from core import logging_setup
from core.auth import ensure_authorized
from core.sdnotify import sd_notify
from handlers import register_handlers

logging_setup.setup()

client = TelegramClient(config.session_name, config.api_id, config.api_hash)


async def main():
    await ensure_authorized(client, interactive=sys.stdin.isatty())
    await register_handlers(client)
    sd_notify("READY=1")
    print("Bot started", flush=True)
    await client.run_until_disconnected()

if __name__ == "__main__":
    client.loop.run_until_complete(main())
