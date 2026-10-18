# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), versions follow [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-10-18

First public release.

### Added
- Delivery modes: post at once (`instant`) or send a digest of headlines every N hours (`digest`); `/mode`, `/digest [hours|now]`.
- Quiet hours in the owner's timezone: stories are queued and sent as a digest when the window ends; `/quiet`, `/tz`.
- Muted words: a post containing one is skipped with reason `muted`; `/mute`, `/unmute`.
- English and Russian messages for the owner, `LANGUAGE` and `/lang`.
- Original formatting (bold, italic, links, quotes, spoilers) is preserved when it fits the message limit.
- `/add` validates input: users, bots, groups and invite links are rejected with an explanation.
- The database schema and base tables are created automatically on a fresh install (migration `000`).
- Docker Compose with PostgreSQL and a local llama.cpp embeddings server.
- Hardened systemd unit with watchdog, failure notifications, daily backups and a monthly restore check.
- `/stats` shows stories queued for a digest.

### Changed
- Short posts are no longer treated as duplicates of a longer post just because all their words appear in it.
- English promo lines and ad markers (`#ad`, `sponsored by`, `promo code`) are recognised.
- Configuration names are upper-case (`TARGET_CHAT_ID`, `OWNER_ID`, ...); lower-case names still work.
- The default language is English; set `LANGUAGE=ru` to keep Russian messages.
- Python 3.12+ is supported.

### Security
- No credentials or private addresses in the code: `DB_PASSWORD` is required, the embeddings URL comes from `EMBEDDINGS_URL`.
- A service without a terminal exits with code 3 instead of waiting for a phone number when the session is not authorized.

[1.0.0]: https://github.com/MartyStev/LentaBox/releases/tag/v1.0.0
