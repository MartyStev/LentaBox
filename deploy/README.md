# Deployment

Everything here assumes a Linux host with systemd and paths under `/opt/stenabot`. Adjust paths and user names to taste, but keep the hardening options.

## 1. The bot

```bash
sudo useradd --system --home /opt/stenabot --shell /usr/sbin/nologin stenabot
sudo mkdir -p /opt/stenabot/var && sudo chown -R stenabot: /opt/stenabot
# copy the repository to /opt/stenabot, then as the stenabot user:
python3 -m venv /opt/stenabot/.venv
/opt/stenabot/.venv/bin/pip install --require-hashes -r /opt/stenabot/requirements.lock
cp /opt/stenabot/.env.example /opt/stenabot/.env && chmod 600 /opt/stenabot/.env
```

In `.env` set `SESSION_NAME=/opt/stenabot/var/stenabot` — `var/` is the only writable directory in the unit.

**First login happens by hand**, in a terminal, as the service user:

```bash
sudo -u stenabot -- sh -c 'cd /opt/stenabot && .venv/bin/python bot.py'    # phone number and code, then Ctrl+C
```

Then:

```bash
sudo install -m 644 deploy/stenabot.service deploy/stenabot-failure@.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now stenabot
journalctl -u stenabot -f
```

What the unit does:

- `Type=notify`: the bot reports `READY=1` after migrations and handler registration, so a start that fails on the database is a failed start.
- `WatchdogSec=300`: the bot pings systemd every `WATCHDOG_SEC` (60 s). If the event loop hangs, systemd restarts it.
- `Restart=always`, no start limit (the bot waits out database restarts), except **exit code 3** — the session is not authorized, restarting cannot help.
- Hardening: `NoNewPrivileges`, read-only system and code, private `/tmp`, syscall filter, `MemoryMax=1G`.

If the log collector prefers JSON, set `LOG_FORMAT=json`.

## 2. Failure notifications

`stenabot-failure@.service` runs `deploy/notify-failure.sh` when a unit fails. The userbot itself may be the thing that died, so the message goes through the Bot API with a **separate ordinary bot**: create one with @BotFather, press `/start` in it from the owner account, and set in `.env`:

```
NOTIFY_BOT_TOKEN=123456:ABC...
```

Without the token the script only writes to the journal. The token is passed to `curl` through stdin, not in arguments.

## 3. Backups

Install on the **PostgreSQL host** (it can be the same machine).

```bash
sudo install -m 755 deploy/backup/stenabot-backup.sh deploy/backup/stenabot-restore-check.sh /usr/local/bin/
sudo install -m 755 deploy/notify-failure.sh /usr/local/bin/stenabot-notify-failure.sh
sudo install -m 644 deploy/backup/*.service deploy/backup/*.timer /etc/systemd/system/
sudo install -m 600 /dev/null /etc/stenabot-backup.env     # then fill it in, see below
sudo systemctl daemon-reload
sudo systemctl enable --now stenabot-backup.timer stenabot-restore-check.timer
```

`/etc/stenabot-backup.env`:

```
PGDATABASE=stenabot
SCHEMA=stenabot
BACKUP_DIR=/var/backups/stenabot
KEEP_DAYS=14
# optional off-site copy via rsync over ssh (host:/path/ or user@host:/path/); empty = none
OFFSITE=
OFFSITE_KEEP_DAYS=60
# failure notification (same bot as above) and your numeric Telegram id
NOTIFY_BOT_TOKEN=
OWNER_ID=
```

The `postgres` user must be able to read the schema (`PGUSER` if it differs).

- **Daily at 03:30** `pg_dump` writes `stenabot-<time>.dump` (mode 600), checks that the archive lists `posts` data, fails if the dump is less than half the size of the previous one, prunes old files locally and, if `OFFSITE` is set, copies with `rsync` (never `--delete`) and prunes the remote copy.
- **Monthly** the latest dump is restored into a throwaway database `stenabot_check`, and row counts of `posts`, `channels` and `publication_claims` are compared with the live schema. A mismatch or error fails the unit and notifies you. A backup you have never restored is a hope, not a backup.

Restore by hand:

```bash
createdb stenabot_restored && psql -d stenabot_restored -c 'CREATE SCHEMA stenabot'
pg_restore --dbname stenabot_restored --schema stenabot --no-owner /var/backups/stenabot/stenabot-<time>.dump
```
