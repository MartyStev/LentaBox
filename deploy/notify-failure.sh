#!/usr/bin/env bash
# Tell the owner about a unit that failed (OnFailure=). The userbot itself may be dead at that point, so this
# goes through the Bot API with curl and a separate, ordinary bot: create one with @BotFather, press /start in it
# from the owner account, and put its token in NOTIFY_BOT_TOKEN. Without the token the script only logs.
# The token goes to curl through a config on stdin, not in arguments: otherwise it is visible in /proc/<pid>/cmdline.
set -euo pipefail
unit="${1:-unknown}"
if [[ -z "${NOTIFY_BOT_TOKEN:-}" ]]; then
    echo "NOTIFY_BOT_TOKEN is not set: no notification about ${unit}" >&2
    exit 0
fi
: "${OWNER_ID:?}"
[[ "$OWNER_ID" =~ ^[0-9]+$ ]] || { echo "OWNER_ID must be numeric" >&2; exit 2; }
text="⚠️ $(hostname): unit ${unit} failed. Look: journalctl -u ${unit} -n 50"
printf 'url = "https://api.telegram.org/bot%s/sendMessage"\n' "$NOTIFY_BOT_TOKEN" |
    curl -fsS --max-time 10 -K - --data-urlencode "chat_id=${OWNER_ID}" --data-urlencode "text=${text}" >/dev/null
