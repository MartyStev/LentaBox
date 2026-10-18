"""Failure alerts to the owner, rate-limited per identical message."""

import logging
import time

log = logging.getLogger("stenabot.alerts")


class Alerter:
    def __init__(self, client, owner_id, cooldown=600, clock=time.monotonic):
        self._client = client
        self._owner_id = owner_id
        self._cooldown = cooldown
        self._clock = clock
        self._last: dict[str, float] = {}

    async def notify(self, key: str, text: str, cooldown: float | None = None) -> bool:
        """Send an alert unless one was sent for this key recently."""
        now = self._clock()
        wait = self._cooldown if cooldown is None else cooldown
        last = self._last.get(key)
        if last is not None and now - last < wait:
            return False
        self._last[key] = now
        try:
            await self._client.send_message(self._owner_id, f"⚠️ {text}", parse_mode=None)
        except Exception:
            log.exception("Failed to send alert %s", key)
            return False
        return True
