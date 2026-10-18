"""Telegram login that never blocks a service waiting for a phone number nobody can type."""

import logging

log = logging.getLogger("stenabot.auth")

# systemd units use RestartPreventExitStatus=3: restarting cannot fix a missing login
EXIT_UNAUTHORIZED = 3


async def ensure_authorized(client, *, interactive: bool) -> None:
    """Connect; log in through the Telethon dialog only when a terminal is attached.

    Without a terminal (systemd, Docker) an unauthorized session exits with code 3 and a clear message
    instead of crashing on ``input()`` in a restart loop.
    """
    await client.connect()
    if await client.is_user_authorized():
        return
    if not interactive:
        log.error("The Telegram session is not authorized. Run `python bot.py` in a terminal once to log in.")
        raise SystemExit(EXIT_UNAUTHORIZED)
    await client.start()
