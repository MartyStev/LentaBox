"""Settings the owner changes with commands, without restarting the bot.

Values live in memory, are persisted by the command handlers (bot_settings) and loaded at startup.
A stored value that no longer validates is ignored, so a bad row can never stop the bot.
"""

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import config
from core import i18n, quiet
from core.i18n import t

# name -> (type, minimum, maximum, default taken from config)
SCHEMA = {
    "cluster_threshold": (float, 0.5, 0.99, lambda: config.CLUSTER_THRESHOLD),
    "fuzzy_threshold": (float, 50.0, 100.0, lambda: config.FUZZ_DUP_THRESHOLD),
    "autosync": (bool, None, None, lambda: False),
    "language": (str, None, None, lambda: config.LANGUAGE),
    "delivery_mode": (str, None, None, lambda: config.DELIVERY_MODE),
    "digest_hours": (int, 1, 24, lambda: config.DIGEST_HOURS),
    "quiet_hours": (str, None, None, lambda: config.QUIET_HOURS),
    "timezone": (str, None, None, lambda: config.TIMEZONE),
}
CHOICES = {"language": i18n.LANGUAGES, "delivery_mode": ("instant", "digest")}
_values: dict = {}


def _parse_quiet_hours(raw) -> str:
    try:
        return quiet.format_window(quiet.parse_window_strict(str(raw)))
    except ValueError:
        raise ValueError(t("err_quiet_hours")) from None


def _parse_timezone(raw) -> str:
    name = str(raw).strip()
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError):
        raise ValueError(t("err_timezone")) from None
    return name


CUSTOM = {"quiet_hours": _parse_quiet_hours, "timezone": _parse_timezone}


def parse(name: str, raw):
    """Validate and convert a setting value; ValueError (with a message for the owner) on error."""
    if name not in SCHEMA:
        raise ValueError(t("err_unknown_setting", name=name))
    kind, low, high, _ = SCHEMA[name]
    if name in CUSTOM:
        return CUSTOM[name](raw)
    if kind is bool:
        text = str(raw).strip().lower()
        if text in {"on", "1", "true", "yes", "да", "вкл"}:
            return True
        if text in {"off", "0", "false", "no", "нет", "выкл"}:
            return False
        raise ValueError(t("err_on_off"))
    if name in CHOICES:
        choice = str(raw).strip().lower()
        if choice not in CHOICES[name]:
            raise ValueError(t("err_choice", options=", ".join(CHOICES[name])))
        return choice
    value = kind(str(raw).replace(",", "."))
    if low is None or high is None:
        raise ValueError(f"Setting {name} has no numeric range")
    if not low <= value <= high:
        raise ValueError(t("err_range", low=low, high=high))
    return value


def get(name: str):
    if name in _values:
        return _values[name]
    return SCHEMA[name][3]()


def quiet_window():
    """The quiet-hours window as (start, end) or None."""
    return quiet.parse_window(get("quiet_hours"))


def zone() -> ZoneInfo:
    return ZoneInfo(get("timezone"))


def _apply(name: str) -> None:
    if name == "language":
        i18n.set_language(get(name))


def set_value(name: str, raw):
    """Set a value in memory and return it."""
    _values[name] = parse(name, raw)
    _apply(name)
    return _values[name]


def load(stored: dict) -> None:
    """Pick up stored settings; corrupt values are skipped."""
    for name, raw in stored.items():
        try:
            set_value(name, raw)
        except (ValueError, TypeError):
            continue


def reset(name: str) -> None:
    """Return a setting to the value from config."""
    _values.pop(name, None)
    _apply(name)
