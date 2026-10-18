import importlib

import pytest

import config

REQUIRED = {"API_ID": "1", "API_HASH": "h", "TARGET_CHAT_ID": "1", "OWNER_ID": "2", "DB_PASSWORD": "secret"}


def reload_config(monkeypatch, **env):
    for name in ("DB_NAME", "DB_USER", "DB_HOST", "DB_PORT", "DB_SCHEMA", "EMBEDDINGS_URL", "EMBEDDINGS_MODEL",
                 "db_host", "target_chat_id", "owner_id", "db_password", "DELIVERY_MODE", "DIGEST_HOURS",
                 "QUIET_HOURS", "TIMEZONE", "LANGUAGE"):
        monkeypatch.delenv(name, raising=False)
    for name, value in {**REQUIRED, **env}.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)
    return importlib.reload(config)


@pytest.fixture(autouse=True)
def restore_config():
    yield
    importlib.reload(config)


def test_defaults_do_not_point_at_any_private_host(monkeypatch):
    cfg = reload_config(monkeypatch)
    assert cfg.db_config["host"] == "localhost"
    assert cfg.db_config["dbname"] == "stenabot"
    assert cfg.db_config["user"] == "stenabot"
    assert cfg.db_config["schema"] == "stenabot"
    assert cfg.EMBEDDINGS_URL.startswith("http://localhost")
    assert cfg.db_config["password"] == "secret"


def test_database_password_is_required(monkeypatch):
    with pytest.raises(RuntimeError, match="DB_PASSWORD"):
        reload_config(monkeypatch, DB_PASSWORD=None)


def test_lowercase_names_are_still_accepted(monkeypatch):
    cfg = reload_config(monkeypatch, TARGET_CHAT_ID=None, target_chat_id="77")
    assert cfg.target_chat_id == 77


def test_uppercase_wins_over_lowercase(monkeypatch):
    monkeypatch.setenv("owner_id", "5")
    cfg = reload_config(monkeypatch, OWNER_ID="9")
    assert cfg.owner_id == 9


def test_invalid_integer_is_reported_by_name(monkeypatch):
    with pytest.raises(RuntimeError, match="OWNER_ID"):
        reload_config(monkeypatch, OWNER_ID="abc")


def test_embeddings_url_comes_from_environment(monkeypatch):
    cfg = reload_config(monkeypatch, EMBEDDINGS_URL="http://emb.example:9000/v1/embeddings")
    assert cfg.EMBEDDINGS_URL == "http://emb.example:9000/v1/embeddings"


@pytest.mark.parametrize("name, value", [
    ("DELIVERY_MODE", "hourly"),
    ("DIGEST_HOURS", "0"),
    ("DIGEST_HOURS", "25"),
    ("DIGEST_HOURS", "three"),
    ("QUIET_HOURS", "late"),
    ("TIMEZONE", "Mars/Olympus"),
    ("LANGUAGE", "de"),
])
def test_invalid_delivery_settings_stop_the_bot_at_startup(monkeypatch, name, value):
    with pytest.raises(RuntimeError, match=name):
        reload_config(monkeypatch, **{name: value})


def test_valid_delivery_settings_are_accepted(monkeypatch):
    cfg = reload_config(monkeypatch, DELIVERY_MODE="Digest", DIGEST_HOURS="6", QUIET_HOURS="23:00-08:00",
                        TIMEZONE="Europe/Moscow", LANGUAGE="RU")
    assert (cfg.DELIVERY_MODE, cfg.DIGEST_HOURS, cfg.QUIET_HOURS, cfg.TIMEZONE, cfg.LANGUAGE) == (
        "digest", 6, "23:00-08:00", "Europe/Moscow", "ru")
