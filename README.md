# LentaBox

[![CI](https://github.com/MartyStev/LentaBox/actions/workflows/ci.yml/badge.svg)](https://github.com/MartyStev/LentaBox/actions/workflows/ci.yml) [![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) ![Python 3.12+](https://img.shields.io/badge/python-3.12%2B-blue.svg)

[English](README.md) · [Русский](README.ru.md)

A Telegram userbot that reads the channels you choose, drops duplicate news and posts every story to your target chat **once** — with a link to the original.

News channels repeat each other all day. LentaBox compares every new post with what it has already published (exact text, reposts, fuzzy text, and embedding similarity of the *story*), so one event appears in your feed one time, no matter how many channels cover it.

- **Deduplication that understands stories**, not just identical text: embeddings are clustered, and a story is posted at most once per sliding 24-hour window.
- **Exactly-once publishing.** A story is reserved in PostgreSQL before it is sent and confirmed in one transaction afterwards. If the outcome of a send is unknown, the bot does *not* retry blindly — it asks you ([unknown outcome](#unknown-send-outcome)).
- **Instant or digest delivery**, plus **quiet hours**: post at once, or collect headlines and send a digest every N hours; nothing is posted at night.
- **Muted words**, original **formatting is preserved** (bold, links, quotes), media is re-sent where Telegram allows it.
- **Channel management from the chat**: follow the account's own subscriptions and folders, with optional autosync.
- **Built to run unattended**: backfill after downtime, stall and silence alerts, systemd watchdog, single-instance lock, migrations, backups with restore checks.
- Messages to the owner in **English or Russian** (`/lang`).

## How it works

```
channels ──▶ Telethon (your account) ──▶ clean text ──▶ checks ──▶ story cluster ──▶ claim ──▶ target chat
                                                         │                                  └─▶ digest queue ──▶ digest
                                                         └─▶ skipped, with a recorded reason (/why)
```

Checks, in order: muted word → too old → advertisement → exact duplicate → repost of an already published original → fuzzy duplicate → too short → embedding similarity to recent story clusters (threshold `0.92`, cluster centroid is a moving average). Before posting, the story is *claimed* so two channels publishing the same event at the same moment cannot both win.

Every decision, including every skip, is stored with an excerpt, so thresholds can be tuned from real data: `/stats`, `/stats channels`, `/why <post link>`.

## Requirements

- Python 3.12 or 3.13
- PostgreSQL (developed and tested on 18). The database user needs the right to create a schema, or an existing schema it owns.
- An OpenAI-compatible **embeddings server**, for example llama.cpp (`llama-server --embedding`) with `nomic-embed-text`, or any service exposing `/v1/embeddings`.
- Telegram API credentials (`API_ID`, `API_HASH`) from <https://my.telegram.org>, and a Telegram account for the userbot.

## Quick start with Docker

Docker Compose runs the bot, PostgreSQL and a local embeddings server (llama.cpp with `nomic-embed-text`):

```bash
cp .env.example .env              # fill in API_ID, API_HASH, TARGET_CHAT_ID, OWNER_ID, DB_PASSWORD
docker compose run --rm bot       # first start: log in to Telegram (phone number and code), then Ctrl+C
docker compose up -d
docker compose logs -f bot
```

The session is stored in the `session` volume. Already have an embeddings server? Remove the `embeddings` service and set `EMBEDDINGS_URL`.

## Quick start without Docker

```bash
python3 -m venv .venv
.venv/bin/pip install --require-hashes -r requirements.lock
cp .env.example .env          # fill in API_ID, API_HASH, TARGET_CHAT_ID, OWNER_ID, DB_PASSWORD, ...
```

1. Create a database user and database. The bot creates the schema and the tables itself on the first start:

   ```sql
   CREATE ROLE stenabot LOGIN PASSWORD '...';
   CREATE DATABASE stenabot OWNER stenabot;
   ```

2. Start the embeddings server and point `EMBEDDINGS_URL` at it.
3. Log in once, **in a terminal** — Telethon asks for the phone number and the code:

   ```bash
   .venv/bin/python bot.py
   ```

   Without a terminal (systemd, Docker) an unauthorized session exits with code `3` instead of hanging.
4. Send `/menu` to the bot from the owner account (`OWNER_ID`), then connect channels with `/subs` and `/track`, or `/add @channel`.

The bot posts to `TARGET_CHAT_ID` as the userbot account, so that account must be allowed to write there (for a channel — be an admin). `OWNER_ID` is the only account the bot obeys and alerts; it can be a different account from the userbot.

## Configuration

Everything deployment-specific comes from environment variables (or `.env`). Upper-case names are canonical; lower-case ones are accepted for old installs.

| Variable | Default | Meaning |
|---|---|---|
| `API_ID`, `API_HASH` | — | Telegram application credentials |
| `SESSION_NAME` | `stenabot_session` | Telethon session file (a path is fine) |
| `TARGET_CHAT_ID` | — | Where news are posted |
| `OWNER_ID` | — | The only account allowed to control the bot |
| `DB_HOST` `DB_PORT` `DB_NAME` `DB_USER` | `localhost` `5432` `stenabot` `stenabot` | PostgreSQL |
| `DB_PASSWORD` | — (required) | |
| `DB_SCHEMA` | `stenabot` | Schema for all tables |
| `EMBEDDINGS_URL` | `http://localhost:8081/v1/embeddings` | OpenAI-compatible embeddings endpoint |
| `EMBEDDINGS_MODEL` | `nomic-embed-text` | |
| `LANGUAGE` | `en` | `en` or `ru`; changed at runtime with `/lang` |
| `DELIVERY_MODE` | `instant` | `instant` or `digest` |
| `DIGEST_HOURS` | `3` | Digest period, 1–24 |
| `QUIET_HOURS` | empty | e.g. `23:00-08:00` |
| `TIMEZONE` | `UTC` | IANA name for quiet hours |
| `LOG_FORMAT` / `LOG_LEVEL` | `text` / `INFO` | `json` for log collectors |

Delivery settings, language and thresholds can all be changed from the chat and are stored in the database, so they survive restarts. Intervals, windows and limits live in [`config.py`](config.py) with comments.

> **Upgrading from an older version:** the default language is now English. To keep Russian messages set `LANGUAGE=ru` or send `/lang ru`. Lower-case variable names (`target_chat_id`, `owner_id`, …) still work. The database password no longer has a default: set `DB_PASSWORD`. New migrations `000` (base tables, a no-op on existing databases), `006` (muted words) and `007` (digest queue) are applied automatically at start.

## Commands

All commands work only from `OWNER_ID`. The bot runs as a regular account, so instead of buttons it uses numbers from the last list.

| Command | What it does |
|---|---|
| `/menu` | All commands |
| `/subs [new\|tracked\|text\|folder Name] [page N]` | The account's subscriptions (✅ tracked, ⬜ not) |
| `/track 1 3 5-9`, `/track all`, `/track folder Name` | Start following; `/untrack …` stops |
| `/folders`, `/sync [apply]`, `/autosync [on\|off]` | Folders; compare subscriptions with tracked channels; follow subscriptions automatically |
| `/list`, `/add <link>`, `/remove <link>` | Tracked channels (with posts in 24 h); add or remove by `@name` / `t.me` link |
| `/mode [instant\|digest]`, `/digest [hours\|now]` | Post at once or as a digest; digest period; send it now |
| `/quiet [HH:MM-HH:MM\|off]`, `/tz [Zone/City]` | Quiet hours and their timezone |
| `/mute [word]`, `/unmute <word>` | Muted words (case-insensitive substring) |
| `/lang [ru\|en]` | Language of the bot's messages |
| `/stats [channels]`, `/why <id\|link>` | Decisions in the last 24 h; why a post was posted or skipped |
| `/threshold [cluster\|fuzzy value\|reset]` | Deduplication thresholds without a restart |
| `/pending [id\|page N]`, `/pending resolve <id> sent\|failed` | Sends with an unknown outcome |

Autosync only removes channels that were connected from subscriptions (`source = 'sync'`); channels added with `/add` are never touched, and channels you disconnected with `/untrack` or `/remove` are not brought back (re-add them with `/track`).

## Delivery: instant, digest, quiet hours

- **instant** (default): a new story is posted as soon as it passes the checks, with its original formatting and media.
- **digest**: stories are queued and sent as one message of headlines with links every `DIGEST_HOURS`. `/digest now` sends the queue immediately.
- **quiet hours**: in the window, nothing is posted at once; stories wait in the same queue and are sent as a digest when the window ends.

A queued story counts as published for deduplication from the moment it is queued (post, claim and queue row are written in one transaction), so it cannot be posted a second time. A digest is marked as sent only after every part reached the chat; if a part fails, the whole digest is retried — a repeated headline is better than a lost one.

## Reliability

- A message that cannot be processed `MAX_PROCESS_ATTEMPTS` times over at least `GIVEUP_MIN_AGE_SEC` is skipped (`error_giveup`) so one bad message cannot block a channel.
- Sends are paced (`SEND_MIN_INTERVAL_SEC`) so a backlog does not become a flood; messages older than `BACKFILL_MAX_AGE_HOURS` are skipped after long downtime.
- Cursors are compared with the channels every `STALL_CHECK_SEC`; a stalled channel and a long silence (`SILENCE_ALERT_HOURS`) are reported to the owner. Identical alerts are throttled.
- One instance per database (advisory lock); if the lock is lost the process exits. DB access goes through a connection pool; embeddings requests are retried.
- Migrations in `db/migrations` are applied at start and checksummed. **Never edit an applied migration — add the next number.**

### Unknown send outcome

Before sending, the bot reserves the story in `publication_claims`. After Telegram confirms, the post, the cluster mark and the claim are saved in one transaction. If the connection drops after the send, or the database refuses, the claim stays `pending`: retrying automatically could duplicate the post. The bot tells you; check the target chat and close the claim:

- `/pending resolve <id> sent` — the post is there; it will not be sent again.
- `/pending resolve <id> failed` — it is not there; the next pass sends it.

A claim older than `CLAIM_EXPIRE_HOURS` (24 h) is closed automatically as `expired` and reported: the news is stale, the channel moves on.

## Deployment

See [`deploy/README.md`](deploy/README.md): hardened systemd unit (watchdog, `NoNewPrivileges`, read-only filesystem), failure notifications, daily PostgreSQL backups with off-site copy and a monthly restore check.

## Development

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.lock
.venv/bin/python -m pytest -q                      # unit tests, no network and no database needed
TEST_DB_DSN=postgresql://user@localhost:5432/postgres .venv/bin/python -m pytest -q tests/integration
.venv/bin/ruff check .
.venv/bin/mypy
scripts/relock.sh                                  # rebuild the hashed lock files after editing requirements*.txt (needs uv)
```

Integration tests create a throwaway schema per test and drop it afterwards, so they are safe against a database that holds other data. CI (`.github/workflows/ci.yml`) runs ruff, mypy, all tests on PostgreSQL 18 with an 80 % coverage gate, and `pip-audit`. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Security and responsible use

- A Telethon **session file gives full access to the Telegram account**. It is git-ignored; keep it out of backups you share, and never publish it. If one leaks, terminate it in Telegram → Settings → Devices.
- Use your own `API_ID`/`API_HASH` and follow Telegram's [API Terms of Service](https://core.telegram.org/api/terms). Automating a user account carries the risk of limits or a ban; the bot paces its requests, but you are responsible for how you use it.
- Respect the rights of the channels you read. Stenabot posts a short link back to each original; it is meant for a personal feed, not for republishing other people's content at scale.
- Report vulnerabilities as described in [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE)
