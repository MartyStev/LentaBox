# Contributing

Thanks for helping. Stenabot is a small project: keep changes focused and tested.

## Setup

```bash
python3 -m venv .venv && .venv/bin/pip install --require-hashes -r requirements-dev.lock
cp .env.example .env     # not needed for tests, they set their own environment
```

## Before you open a pull request

```bash
.venv/bin/ruff check .
.venv/bin/mypy
.venv/bin/python -m pytest -q
TEST_DB_DSN=postgresql://user@localhost:5432/postgres .venv/bin/python -m pytest -q tests/integration
```

CI runs the same checks on PostgreSQL 18 and requires 80 % coverage.

## Rules of the road

- **Tests first.** New behaviour comes with a test that failed before the change. Code that touches SQL needs an integration test (`tests/integration`): mocks cannot show that a query is right.
- **Migrations are append-only.** Never edit an applied file in `db/migrations`; add the next number. Make them safe for tables that already hold data.
- **Everything the bot says goes through the catalog.** Add a key to *both* `core/messages/en.py` and `core/messages/ru.py` with the same placeholders (a test checks it). No hard-coded user-facing strings in handlers.
- **Do not weaken exactly-once publishing.** A story is claimed before it is sent, and an unknown send outcome keeps the claim `pending` for a human. If a change touches `handlers/listener.py` or `db/publications.py`, explain how it preserves that.
- **Secrets stay out.** Never commit `.env`, `*.session`, or real chat IDs/tokens. Tests must not read a real `.env` (`STENABOT_DOTENV=0`).
- After editing `requirements*.txt` run `scripts/relock.sh` and commit the lock files.

## Commit messages

`<type>: <description>` with type one of `feat`, `fix`, `refactor`, `docs`, `test`, `chore`, `perf`, `ci`.
