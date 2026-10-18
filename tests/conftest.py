"""Test environment: config.py reads variables at import time, so they are set before test collection.

The tests never read a real .env (STENABOT_DOTENV=0), so production values do not leak into them.
"""

import os

os.environ.setdefault("STENABOT_DOTENV", "0")
os.environ.setdefault("API_ID", "1")
os.environ.setdefault("API_HASH", "test-hash")
os.environ.setdefault("TARGET_CHAT_ID", "1")
os.environ.setdefault("OWNER_ID", "2")
os.environ.setdefault("DB_PASSWORD", "test-password")
# Existing tests assert the Russian texts; i18n tests switch the language explicitly.
os.environ.setdefault("LANGUAGE", "ru")
