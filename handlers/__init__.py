import asyncio
import config
import logging
import db.settings as settings_db
from core import runtime
from core.i18n import t
from core.alerts import Alerter
from db import instance_lock
from db.migrate import run_migrations
from handlers.commands import register_commands
from handlers.listener import register_listener
from handlers.maintenance import (
    autosync_loop, digest_loop, digest_once, expire_claims_loop, instance_lock_loop, purge_loop, silence_loop,
    stall_loop, watchdog_loop,
)
from handlers.subscriptions import register_subscription_commands

log = logging.getLogger("stenabot")


async def register_handlers(client):
    if not await asyncio.to_thread(instance_lock.acquire):
        raise RuntimeError(
            "Another bot instance is already working with this database. "
            "Two userbots at once would publish duplicates."
        )
    await asyncio.to_thread(run_migrations)
    runtime.load(await asyncio.to_thread(settings_db.load_all))

    alerter = Alerter(client, config.owner_id, cooldown=config.ALERT_COOLDOWN_SEC)

    async def send_start_message():
        try:
            await client.send_message(
                config.owner_id,
                t("start_message")
            )
        except Exception as e:
            log.warning("Failed to send the startup message: %s", e)

    client.loop.create_task(send_start_message())

    refresh_channels, _, backfill_loop = register_listener(client, alerter)
    client.loop.create_task(backfill_loop())
    async def flush_digest():
        return await digest_once(client, alerter, force=True)

    register_commands(client, config.owner_id, on_channels_changed=refresh_channels, flush_digest=flush_digest)
    manager = register_subscription_commands(
        client, config.owner_id, on_channels_changed=refresh_channels,
    )
    client.loop.create_task(autosync_loop(manager, alerter))
    client.loop.create_task(silence_loop(alerter))
    client.loop.create_task(instance_lock_loop(alerter))
    client.loop.create_task(stall_loop(client, alerter))
    client.loop.create_task(expire_claims_loop(alerter))
    client.loop.create_task(purge_loop())
    client.loop.create_task(digest_loop(client, alerter))
    client.loop.create_task(watchdog_loop())
