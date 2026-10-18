"""English texts. Keys and placeholders must match ru.py (tests/test_i18n.py checks it)."""

MESSAGES = {
    "lang_usage": "Usage: /lang ru|en (now: {language})",
    "lang_set": "Message language: {language}",
    "mute_added": "✅ Muted word added: {word}",
    "mute_exists": "ℹ️ Already muted: {word}",
    "mute_limit": "❌ Too many muted words (maximum {limit})",
    "mute_invalid": "❌ A word must be {min} to {max} characters long",
    "mute_removed": "✅ Muted word removed: {word}",
    "mute_not_found": "❌ No such muted word: {word}",
    "mute_list": (
        "🔇 Muted words ({count}):\n{words}\n"
        "A post containing any of them is not published. "
        "Add: /mute word · remove: /unmute word"
    ),
    "mute_empty": "No muted words. Add one: /mute word",
    "digest_header": "📰 Digest · stories: {count}",
    "digest_link": "original",
    "err_unknown_setting": "Unknown setting: {name}",
    "err_on_off": "Expected on or off",
    "err_range": "The value must be between {low} and {high}",
    "err_choice": "Allowed: {options}",
    "err_quiet_hours": "Expected HH:MM-HH:MM, for example 23:00-08:00, or off",
    "err_timezone": "Unknown timezone. Example: Europe/Moscow, UTC",
    "alert_digest_failed": "Could not send the digest, will retry on the next check: {error}",
    "mode_show": (
        "Delivery mode: {mode}\n"
        "/mode instant - publish at once · /mode digest - a digest of headlines every {hours} h"
    ),
    "mode_set": "✅ Delivery mode: {mode}",
    "digest_show": "Digest period: {hours} h · queued: {queued}\nChange: /digest 6 · send now: /digest now",
    "digest_set": "✅ Digest period: {hours} h",
    "digest_sent": "✅ Stories sent: {count}",
    "digest_empty": "The digest queue is empty",
    "quiet_show": "Quiet hours: {window} ({zone})\nChange: /quiet 23:00-08:00 · turn off: /quiet off",
    "quiet_off_show": "Quiet hours are off. Turn on: /quiet 23:00-08:00",
    "quiet_set": "✅ Quiet hours: {window} ({zone}). During that time news are queued and sent as a digest afterwards",
    "quiet_cleared": "✅ Quiet hours are off",
    "tz_show": "Timezone: {zone}\nChange: /tz Europe/Moscow",
    "tz_set": "✅ Timezone: {zone}",
    "menu_text": (
        "Available commands:\n"
        "/menu - show this message\n\n"
        "Channels:\n"
        "/subs [new | tracked | text | folder Name] [page N] - the account's subscriptions\n"
        "/track <numbers | all | folder Name> - connect from the /subs list\n"
        "/untrack <numbers | all | folder Name> - disconnect\n"
        "/folders - the account's folders\n"
        "/sync [apply] - compare subscriptions with tracked channels\n"
        "/autosync [on|off] - follow subscriptions automatically\n"
        "/list - tracked channels\n"
        "/add <link> - add a channel by hand\n"
        "/remove <link> - remove a channel\n\n"
        "Delivery and filters:\n"
        "/mode [instant|digest] - publish at once or as a digest\n"
        "/digest [hours | now] - digest period, or send it now\n"
        "/quiet [HH:MM-HH:MM | off] - quiet hours\n"
        "/tz [Zone/City] - timezone\n"
        "/mute [word] - muted words: list or add\n"
        "/unmute <word> - remove a muted word\n"
        "/lang [ru|en] - message language\n\n"
        "Diagnostics:\n"
        "/stats [channels] - dedup statistics for 24h\n"
        "/why <message_id | link> - why a decision was made\n"
        "/threshold [cluster|fuzzy value] - dedup thresholds\n"
        "/pending [id | page N] - publications to check\n"
        "/pending resolve <id> sent|failed - close a claim after checking"
    ),
    "list_empty": "The channel list is empty. Connect channels: /subs, /add <link>",
    "list_count": "{count} in 24h",
    "list_header": "📋 Tracked channels: {count}",
    "list_footer": "🔄 — connected from subscriptions (follows autosync)",
    "add_usage": "Usage: /add <link>",
    "add_not_channel": "❌ That does not look like a channel. Use @name or a https://t.me/name link",
    "add_invite": (
        "❌ Private channels by invite link cannot be added. "
        "Join the channel yourself, then connect it with /subs and /track."
    ),
    "add_not_broadcast": "❌ That is not a channel (a user, bot or group): only channels are read",
    "add_ok": "✅ Channel added: {label}",
    "add_error": "❌ Could not add: {error}",
    "remove_usage": "Usage: /remove <link>",
    "remove_ok": "🗑 Channel removed",
    "remove_error": "❌ Could not remove: {error}",
    "stats_channels_header": "📊 By channel, 24h (published / skipped):",
    "stats_no_data": "• no data yet",
    "stats_header": "📊 Statistics for 24h:",
    "stats_total": "Decisions in total: {count}",
    "stats_sent": "Published: {count}",
    "stats_queued": "Queued for digest: {count}",
    "stats_skipped": "Skipped: {count}",
    "stats_reasons": "Reasons:",
    "stats_error": "❌ /stats failed: {error}",
    "why_usage": "Usage: /why <message_id | post link>",
    "why_none": "No records for message_id={id}.",
    "why_header": "🔎 Why for message_id={id}:",
    "why_error": "❌ /why failed: {error}",
    "threshold_show": (
        "Cluster threshold (cosine): {cluster} (default {cluster_default})\n"
        "Fuzzy threshold (0-100): {fuzzy} (default {fuzzy_default})\n"
        "Change: /threshold cluster 0.9 · /threshold fuzzy 85 · /threshold reset"
    ),
    "threshold_reset": "Thresholds reset to the values from config.py",
    "threshold_usage": "Usage: /threshold cluster|fuzzy <value> | reset",
    "threshold_save_failed": "❌ Could not save the threshold",
    "pending_resolve_usage": (
        "Usage: /pending resolve <id> sent|failed\n"
        "sent - the post is in the target chat, failed - it is not there (the bot will send it again)"
    ),
    "pending_resolve_failed": "❌ Could not close the claim, see the logs.",
    "pending_not_found": "The claim was not found or is already closed.",
    "pending_meaning_sent": "marked as sent, it will not be sent again",
    "pending_meaning_failed": "removed, the send will be retried on the next pass",
    "pending_resolved": "✅ Claim #{id} {meaning}.",
    "pending_usage": "Usage: /pending [id | page N]",
    "pending_empty": "No claims with an unknown outcome.",
    "pending_header": "⏳ Publications to check:",
    "pending_source": "Source: {channel}:{message}",
    "pending_next_page": "Next page: /pending page {page}",
    "pending_footer": "Compare the post with the target chat, then: /pending resolve <id> sent|failed",
    "pending_list_error": "❌ Could not get the list of claims.",
    "truncated_mark": "\n\n… Text shortened.",
    "footer_channel": "Channel",
    "footer_original": "Original",
    "unknown_channel": "unknown",
    "start_message": "🚀 The bot is running and listening to the channels.\n/menu — list of commands",
    "alert_send_unknown": "The outcome of a send is unknown (claim #{claim_id}). Check the target chat and /pending.",
    "alert_process_error": "Processing error {channel}:{message}: {error}",
    "alert_giveup": "Message {channel}:{message} was skipped after {attempts} failed attempts.",
    "names_more": " and {extra} more",
    "folder_none": "no folders",
    "folder_not_found": "Folder “{name}” not found. Available: {known}",
    "scope_folder": "folder “{title}”",
    "scope_filter": "filter “{query}”",
    "scope_all": "all",
    "scope_last": "the last /subs list",
    "scope_selection": "selection",
    "subs_nothing": "Nothing found ({label}).",
    "subs_no_page": "There is no page {page}, pages in total: {pages}",
    "subs_header": "📡 The account's subscriptions ({label}): {count}, connected {tracked}. Page {page}/{pages}",
    "subs_next": "Next: /subs {query} page {page}",
    "subs_footer": "Connect: /track 1 3 5-9 or /track all · Disconnect: /untrack 2 4 · Folders: /folders",
    "track_first": "Run /subs first to see the channel numbers",
    "track_usage": "Usage: /track <numbers | all | folder Name>",
    "untrack_usage": "Usage: /untrack <numbers | all | folder Name>",
    "track_already": "All channels in the selection ({scope}) are already connected.",
    "track_done": "✅ Connected ({scope}): {count}\n{names}",
    "untrack_none": "Nothing in the selection ({scope}) was connected.",
    "untrack_done": (
        "🗑 Disconnected ({scope}): {count}\n{names}\n"
        "Autosync will not bring them back; use /track to connect them again."
    ),
    "folders_none": "The account has no chat folders.",
    "folders_header": "📁 The account's folders:",
    "folders_item": "• {title}: channels {count}, not connected {new}",
    "folders_footer": "Open: /subs folder Name · Connect: /track folder Name",
    "sync_done_title": "✅ Synchronised",
    "sync_pending_title": "🔄 Pending changes",
    "sync_nothing": "Everything is in sync: no new subscriptions or unsubscriptions.",
    "sync_apply_hint": "Apply: /sync apply",
    "sync_added": "➕ New subscriptions: {count}",
    "sync_removed": "➖ Unsubscribed: {count}",
    "autosync_on_word": "on",
    "autosync_off_word": "off",
    "autosync_show": (
        "Autosync is {state}. When on, it connects the account's new subscriptions every {minutes} min "
        "and removes channels the account has left "
        "(except those added with /add and disconnected with /untrack).\n"
        "Switch: /autosync on | off"
    ),
    "autosync_off": "Autosync is off.",
    "autosync_enabled_title": "Autosync is on. Right now",
    "autosync_report_title": "Subscription autosync",
    "command_failed": "❌ /{name} failed, see the logs.",
    "sel_empty": "No numbers given",
    "sel_bad_number": "Not a number: {token}",
    "sel_out_of_range": "Number out of range 1-{size}: {token}",
    "alert_silence": "No publications for {hours} h. Check the channels, the embeddings server and /stats.",
    "alert_lock_lost": "The instance lock is lost, the bot is shutting down.",
    "alert_stall": (
        "Channel {channel} has been stuck for {hours} h on message {cursor}, the channel already has {latest}. "
        "Check /pending and the log."
    ),
    "alert_claims_expired": (
        "Closed claims with an unknown outcome: {count} "
        "(older than {hours} h). They will not be retried, the channels move on."
    ),
}
