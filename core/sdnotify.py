"""systemd notifications (READY=1, WATCHDOG=1) over NOTIFY_SOCKET, without dependencies."""

import logging
import os
import socket

log = logging.getLogger("stenabot.sdnotify")


def sd_notify(state: str = "WATCHDOG=1") -> bool:
    """Send a state to systemd; without NOTIFY_SOCKET (manual run, tests) quietly return False."""
    path = os.environ.get("NOTIFY_SOCKET")
    if not path:
        return False
    address = "\0" + path[1:] if path.startswith("@") else path
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM) as sock:
            sock.connect(address)
            sock.sendall(state.encode())
        return True
    except OSError as exc:
        log.debug("sd_notify failed: %s", exc)
        return False
