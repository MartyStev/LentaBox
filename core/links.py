import re


def source_link(username, channel_id, message_id):
    username = (username or "").strip().lstrip("@")
    if username and re.fullmatch(r"[A-Za-z0-9_]+", username):
        return f"https://t.me/{username}/{message_id}"

    channel_id = str(channel_id)
    if channel_id.startswith("-100") and channel_id[4:].isdigit():
        return f"https://t.me/c/{channel_id[4:]}/{message_id}"
    return None
