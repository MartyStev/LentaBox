"""Bot settings. Everything that depends on the deployment is read from environment variables (or a .env file).

UPPER-CASE names: TARGET_CHAT_ID, OWNER_ID, DB_PASSWORD, etc. Lower case
(target_chat_id, owner_id) is accepted as a fallback for older installations.
The remaining constants are thresholds and intervals; they can be changed right here.
"""

import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

from core.quiet import parse_window_strict

if os.getenv("STENABOT_DOTENV", "1") != "0":
    load_dotenv()


def _lookup(name: str) -> str | None:
    for candidate in (name.upper(), name.lower()):
        value = os.getenv(candidate)
        if value not in (None, ""):
            return value
    return None


def _get_env(name: str, default: str | None = None) -> str:
    value = _lookup(name)
    if value is None:
        if default is None:
            raise RuntimeError(f"Missing required env var: {name.upper()}")
        return default
    return value


def _get_int_env(name: str, default: int | None = None) -> int:
    value = _lookup(name)
    if value is None:
        if default is None:
            raise RuntimeError(f"Missing required env var: {name.upper()}")
        return default
    try:
        return int(value)
    except ValueError as e:
        raise RuntimeError(f"Invalid int env var {name.upper()}: {value}") from e


# Telegram: application credentials (https://my.telegram.org) and the Telethon session file name
session_name = _get_env("session_name", "stenabot_session")
api_id = _get_int_env("api_id")
api_hash = _get_env("api_hash")
# The chat that receives the news, and the owner (the only one who controls the bot)
target_chat_id = _get_int_env("target_chat_id")
owner_id = _get_int_env("owner_id")


# PostgreSQL
db_config = {
    "dbname": _get_env("db_name", "stenabot"),
    "user": _get_env("db_user", "stenabot"),
    "password": _get_env("db_password"),
    "host": _get_env("db_host", "localhost"),
    "port": _get_int_env("db_port", 5432),
    "schema": _get_env("db_schema", "stenabot"),
}


BODY_LIMIT = 200     # text used for fuzzy comparison and embeddings

CAPTION_LIMIT = 900  # safely below the Telegram limit


# OpenAI-compatible embeddings server (e.g. llama.cpp with nomic-embed-text)
EMBEDDINGS_URL = _get_env("embeddings_url", "http://localhost:8081/v1/embeddings")
EMBEDDINGS_MODEL = _get_env("embeddings_model", "nomic-embed-text")
# === CLUSTERING ===

# Cosine similarity threshold
# 0.90  - lenient (more grouping)
# 0.92  - optimal for news
# 0.95  - strict (near-duplicates)
CLUSTER_THRESHOLD = 0.92

# A single news item (cluster) is published at most once per this sliding window.
# The window used to be a calendar day: a story at 23:55 and its repeat at 00:05 both went through.
CLUSTER_WINDOW_HOURS = 24

# === FUZZY DEDUP ===
# How many of the most recently sent posts to check for an exact full-text match
EXACT_WINDOW_SIZE = 500
# Text similarity threshold (RapidFuzz token_set_ratio, 0..100)
FUZZ_DUP_THRESHOLD = 88
# How many of the most recently sent posts to check for a fuzzy match
FUZZ_WINDOW_SIZE = 300

# Backfilling messages after downtime: at most 500 messages per channel
# per pass. The next pass continues from the saved cursor.
BACKFILL_INTERVAL_SEC = 60
BACKFILL_BATCH_SIZE = 500
BACKFILL_SETTLE_SEC = 5
# Messages older than this are skipped during backfill (too_old):
# after downtime the feed should not fill up with stale news.
BACKFILL_MAX_AGE_HOURS = 12
# At most one send to the target chat per this many seconds (queue draining, FloodWait).
SEND_MIN_INTERVAL_SEC = 3

# === LANGUAGE ===
# Language of messages to the owner: en or ru. Changed with the /lang command, no restart needed.
LANGUAGE = _get_env("language", "en").strip().lower()
if LANGUAGE not in ("en", "ru"):
    raise RuntimeError(f"LANGUAGE must be en or ru, got {LANGUAGE!r}")

# === DELIVERY ===
# instant - publish right away; digest - accumulate and send a headline digest every DIGEST_HOURS hours.
# Changed with the /mode command, the period with /digest.
DELIVERY_MODE = _get_env("delivery_mode", "instant").strip().lower()
if DELIVERY_MODE not in ("instant", "digest"):
    raise RuntimeError(f"DELIVERY_MODE must be instant or digest, got {DELIVERY_MODE!r}")
DIGEST_HOURS = _get_int_env("digest_hours", 3)
if not 1 <= DIGEST_HOURS <= 24:
    raise RuntimeError(f"DIGEST_HOURS must be between 1 and 24, got {DIGEST_HOURS}")
# Quiet hours "23:00-08:00" (in the TIMEZONE time zone): nothing is published immediately during this time;
# it accumulates and is sent as a digest afterwards. Empty - disabled. The /quiet command.
QUIET_HOURS = (_lookup("quiet_hours") or "").strip()
TIMEZONE = _get_env("timezone", "UTC")
# A typo here would otherwise surface inside the handling of every single message
try:
    parse_window_strict(QUIET_HOURS)
except ValueError as exc:
    raise RuntimeError(f"QUIET_HOURS is invalid: {exc}") from exc
try:
    ZoneInfo(TIMEZONE)
except (ZoneInfoNotFoundError, ValueError, OSError) as exc:
    raise RuntimeError(f"TIMEZONE is not a known IANA timezone: {TIMEZONE!r}") from exc
# Maximum number of stories in one digest and the pause between its parts
DIGEST_BATCH = 300
DIGEST_PART_PAUSE_SEC = 2
DIGEST_CHECK_SEC = 60
# Sent digest queue rows are kept for this many days
DIGEST_RETENTION_DAYS = 14

# === OPERATIONS ===
# Log format: text (for humans) or json (for a log collector)
LOG_FORMAT = _get_env("log_format", "text")
LOG_LEVEL = _get_env("log_level", "INFO")
# How often to report WATCHDOG=1 to systemd; WatchdogSec in the unit must be noticeably larger
WATCHDOG_SEC = 60

# === FILTERS AND CLEANING ===
# Ads are filtered out by explicit markers (erid, #реклама, промокод, etc.).
AD_FILTER_ENABLED = True
# How many characters of text to store in bot_decisions.excerpt
EXCERPT_LIMIT = 200

# Owner's stop words (/mute): word length and total limit
MUTE_WORD_MIN = 2
MUTE_WORD_MAX = 64
MUTE_WORDS_LIMIT = 100

# === CLUSTER CENTROID ===
CENTROID_UPDATE = True
CENTROID_MAX_WEIGHT = 20  # the old centroid's weight does not grow beyond this number of posts

# === RESILIENCE ===
# After this many failed processing attempts the message is skipped,
# so that a single "poison" message does not block the channel.
MAX_PROCESS_ATTEMPTS = 5
GIVEUP_MIN_AGE_SEC = 1800  # ...and only if the failure has lasted at least this long
EMBEDDING_RETRIES = 3

# === OWNER ALERTS ===
ALERT_COOLDOWN_SEC = 600
SILENCE_ALERT_HOURS = 6        # no publications for more than N hours - alert
SILENCE_CHECK_SEC = 1800
# A channel is considered stalled if its cursor has not moved for this many hours
# while new messages have appeared in the channel.
STALL_ALERT_HOURS = 3
STALL_CHECK_SEC = 1800
# A claim with an undetermined outcome older than this is closed automatically
# (state = expired): the news is stale, there is no point in retrying, the channel moves on.
CLAIM_EXPIRE_HOURS = 24
CLAIM_EXPIRE_CHECK_SEC = 1800
# An identical decision for the same message is recorded at most once per this interval.
DECISION_DEDUP_MINUTES = 60
# bot_decisions rows older than this are deleted once a day.
DECISIONS_RETENTION_DAYS = 90

# === SUBSCRIPTION AUTO-SYNC ===
AUTOSYNC_INTERVAL_SEC = 600
SUBS_PAGE_SIZE = 20
