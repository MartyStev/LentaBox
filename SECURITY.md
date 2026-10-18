# Security policy

## Reporting a vulnerability

Please report security problems **privately** — use GitHub's "Report a vulnerability" (Security tab) on this repository, not a public issue. Include what you found, how to reproduce it and the version or commit. You can expect an answer within a few days.

## What matters most here

Stenabot runs as a Telegram **user account**, so the highest-impact problems are:

- anything that exposes the Telethon session file, `API_HASH` or the database password (logs, error messages, backups, scripts);
- anything that lets someone other than `OWNER_ID` control the bot;
- SQL, HTML or command injection through channel names, post texts or command arguments;
- the backup and notification scripts in `deploy/` (they run with elevated rights on the database host).

## If your session leaks

A leaked `*.session` file is full access to the account. Terminate it right away in Telegram → Settings → Devices, then log in again with a new session. Keep `API_HASH` private as well.
