"""Owner-facing texts in Russian and English.

``t(key, **values)`` renders a message in the current language. The language is a runtime setting
(``/lang``), the default comes from ``LANGUAGE`` in the environment. A missing key never breaks a handler:
the key itself is returned and the problem is logged. Texts of the posts themselves are never translated.
"""

import logging

import config
from core.messages import en, ru

log = logging.getLogger("stenabot.i18n")

LANGUAGES = ("en", "ru")
CATALOGS = {"en": en.MESSAGES, "ru": ru.MESSAGES}

_current = config.LANGUAGE


def get_language() -> str:
    return _current


def set_language(language: str) -> None:
    global _current
    if language not in CATALOGS:
        raise ValueError(f"Unknown language: {language}")
    _current = language


def t(key: str, *, lang: str | None = None, **values) -> str:
    template = CATALOGS.get(lang or _current, en.MESSAGES).get(key)
    if template is None:
        log.error("Missing message key %r", key)
        return key
    return template.format(**values) if values else template
