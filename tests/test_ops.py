"""Operations helpers: systemd notifications, watchdog loop, logging format, safe login."""

import asyncio
import json
import logging
import os
import socket
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from core import auth, logging_setup, sdnotify
from handlers import maintenance


def test_sd_notify_is_a_noop_without_socket(monkeypatch):
    monkeypatch.delenv("NOTIFY_SOCKET", raising=False)
    assert sdnotify.sd_notify() is False


def test_sd_notify_sends_the_state_to_the_unix_socket(monkeypatch):
    # unix socket paths are limited to ~100 bytes, pytest's tmp_path is longer on macOS
    with tempfile.TemporaryDirectory(dir="/tmp") as short_dir:
        _check_socket(monkeypatch, os.path.join(short_dir, "n.sock"))


def _check_socket(monkeypatch, path):
    server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    server.bind(path)
    try:
        monkeypatch.setenv("NOTIFY_SOCKET", path)
        assert sdnotify.sd_notify("READY=1") is True
        assert server.recv(64) == b"READY=1"
    finally:
        server.close()


def test_sd_notify_swallows_a_dead_socket(monkeypatch, tmp_path):
    monkeypatch.setenv("NOTIFY_SOCKET", str(tmp_path / "missing.sock"))
    assert sdnotify.sd_notify() is False


async def test_watchdog_loop_pings_systemd_until_cancelled():
    with patch.object(maintenance, "sd_notify") as notify, patch.object(maintenance.config, "WATCHDOG_SEC", 0.01):
        task = asyncio.create_task(maintenance.watchdog_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert notify.call_count >= 2


def test_json_formatter_keeps_extra_fields_and_exceptions():
    record = logging.LogRecord("stenabot.x", logging.ERROR, __file__, 1, "failed %s", ("here",), None)
    record.channel = "-100"
    try:
        raise ValueError("boom")
    except ValueError:
        import sys
        record.exc_info = sys.exc_info()
    entry = json.loads(logging_setup.JsonFormatter().format(record))
    assert entry["level"] == "ERROR" and entry["msg"] == "failed here" and entry["channel"] == "-100"
    assert "ValueError: boom" in entry["exc"]


def test_setup_installs_one_handler_with_the_requested_format(monkeypatch):
    root = logging.getLogger()
    saved, level = root.handlers[:], root.level
    try:
        monkeypatch.setattr(logging_setup.config, "LOG_FORMAT", "json")
        logging_setup.setup()
        logging_setup.setup()
        assert len(root.handlers) == 1
        assert isinstance(root.handlers[0].formatter, logging_setup.JsonFormatter)
    finally:
        root.handlers[:] = saved
        root.setLevel(level)


def fake_client(authorized: bool):
    return SimpleNamespace(
        connect=AsyncMock(), is_user_authorized=AsyncMock(return_value=authorized), start=AsyncMock(),
    )


async def test_authorized_session_just_connects():
    client = fake_client(True)
    await auth.ensure_authorized(client, interactive=False)
    client.connect.assert_awaited_once()
    client.start.assert_not_awaited()


async def test_unauthorized_session_without_terminal_exits_with_code_3():
    client = fake_client(False)
    with pytest.raises(SystemExit) as exc:
        await auth.ensure_authorized(client, interactive=False)
    assert exc.value.code == auth.EXIT_UNAUTHORIZED == 3
    client.start.assert_not_awaited()


async def test_unauthorized_session_in_a_terminal_starts_the_login_dialog():
    client = fake_client(False)
    await auth.ensure_authorized(client, interactive=True)
    client.start.assert_awaited_once()
