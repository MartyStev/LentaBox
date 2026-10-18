"""Backup scripts run under real bash with fake pg_dump/pg_restore/rsync/ssh/curl.

Syntax alone would not show the SIGPIPE trap under pipefail, path validation or the prune exit code.
"""

import os
import stat
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
BACKUP = ROOT / "deploy" / "backup" / "stenabot-backup.sh"
RESTORE = ROOT / "deploy" / "backup" / "stenabot-restore-check.sh"
NOTIFY = ROOT / "deploy" / "notify-failure.sh"
UNIT = ROOT / "deploy" / "stenabot.service"

FAKES = {
    "pg_dump": '''#!/usr/bin/env bash
for a in "$@"; do case "$a" in --file=*) f="${a#--file=}";; esac; done
head -c "${FAKE_DUMP_SIZE:-2000}" /dev/zero > "$f"
''',
    "pg_restore": '''#!/usr/bin/env bash
if [[ "$1" == "--list" ]]; then
  if [[ -n "${FAKE_NO_POSTS:-}" ]]; then echo "; TABLE DATA stenabot channels"; else echo "; TABLE DATA stenabot posts"; fi
  # a long list: grep -q through a pipe used to die of SIGPIPE under pipefail
  for i in $(seq 1 3000); do echo "; filler $i"; done
fi
''',
    "rsync": '#!/usr/bin/env bash\necho "rsync $*" >> "$FAKE_LOG"\n',
    "ssh": '#!/usr/bin/env bash\necho "ssh $*" >> "$FAKE_LOG"\nexit "${FAKE_SSH_RC:-0}"\n',
    "dropdb": '#!/usr/bin/env bash\necho "dropdb $*" >> "$FAKE_LOG"\n',
    "createdb": '#!/usr/bin/env bash\necho "createdb $*" >> "$FAKE_LOG"\n',
    "psql": '''#!/usr/bin/env bash
db="${@: -1}"
echo "psql $*" >> "$FAKE_LOG"
if [[ "$db" == "$FAKE_LIVE_DB" ]]; then echo "${FAKE_LIVE:-5}"; else echo "${FAKE_RESTORED:-5}"; fi
''',
    "curl": '#!/usr/bin/env bash\ncat > "$FAKE_STDIN"\necho "curl $*" >> "$FAKE_LOG"\n',
}


@pytest.fixture
def sandbox(tmp_path):
    bindir, backups, log = tmp_path / "bin", tmp_path / "backups", tmp_path / "calls.log"
    bindir.mkdir()
    for name, body in FAKES.items():
        path = bindir / name
        path.write_text(body)
        path.chmod(path.stat().st_mode | stat.S_IEXEC)
    base_env = {"PATH": f"{bindir}:/usr/bin:/bin", "BACKUP_DIR": str(backups), "PGDATABASE": "services",
                "FAKE_LOG": str(log), "FAKE_LIVE_DB": "services", "FAKE_STDIN": str(tmp_path / "stdin"),
                "HOME": str(tmp_path)}

    def run(script, *args, **env):
        proc = subprocess.run(["bash", str(script), *args], env={**base_env, **env},
                              capture_output=True, text=True, timeout=60)
        calls = log.read_text().splitlines() if log.exists() else []
        return proc, calls, backups
    run.stdin_file = tmp_path / "stdin"
    return run


def test_backup_ok_writes_private_dump_syncs_and_prunes_strictly(sandbox):
    proc, calls, backups = sandbox(BACKUP, OFFSITE="user@nas:/backups/stenabot/")
    assert proc.returncode == 0, proc.stderr
    dumps = list(backups.glob("stenabot-*.dump"))
    assert len(dumps) == 1 and stat.S_IMODE(dumps[0].stat().st_mode) == 0o600           # umask 077
    assert any(c.startswith("rsync -a --") and c.endswith("user@nas:/backups/stenabot/") and "--delete" not in c
               for c in calls)
    prune = next(c for c in calls if c.startswith("ssh"))
    assert prune.startswith("ssh -- user@nas ") and "-maxdepth 1 -type f" in prune and "-mtime +60 -delete" in prune


def test_backup_fails_without_posts_on_suspicious_size_and_on_failed_prune(sandbox):
    proc, _, _ = sandbox(BACKUP, FAKE_NO_POSTS="1")
    assert proc.returncode == 1 and "no posts data" in proc.stderr

    proc, _, backups = sandbox(BACKUP, FAKE_DUMP_SIZE="10000")                          # first dump: the baseline
    assert proc.returncode == 0
    first = next(backups.glob("stenabot-*.dump"))
    first.rename(backups / "stenabot-00000000-0000.dump")
    proc, _, _ = sandbox(BACKUP, FAKE_DUMP_SIZE="100")
    assert proc.returncode == 1 and "suspicious" in proc.stderr

    proc, calls, _ = sandbox(BACKUP, OFFSITE="nas:/backups/stenabot", FAKE_SSH_RC="3", FAKE_DUMP_SIZE="10000")
    assert proc.returncode == 3 and any(c.startswith("ssh") for c in calls)             # a failed prune fails the unit


@pytest.mark.parametrize("env", [
    {"KEEP_DAYS": "two-weeks"},
    {"SCHEMA": "x; drop table posts"},
    {"OFFSITE": "nas:/backups/with space"},
    {"OFFSITE": "-oProxyCommand=evil:/backups"},
    {"OFFSITE": "nas:-delete-everything"},
    {"OFFSITE": "nas:relative/path"},
])
def test_backup_rejects_unsafe_settings_before_touching_anything(sandbox, env):
    proc, calls, backups = sandbox(BACKUP, **env)
    assert proc.returncode == 2, proc.stderr
    assert not any(c.startswith(("rsync", "ssh")) for c in calls)


def test_restore_check_compares_counts_and_cleans_up(sandbox):
    sandbox(BACKUP)
    proc, calls, _ = sandbox(RESTORE, CHECK_DB="stenabot_check")
    assert proc.returncode == 0, proc.stderr
    assert "posts: live 5, restored 5" in proc.stdout
    assert calls[-1] == "dropdb --if-exists stenabot_check"                              # trap on EXIT
    create = next(i for i, c in enumerate(calls) if "CREATE SCHEMA stenabot" in c)
    count = next(i for i, c in enumerate(calls) if "SELECT COUNT(*)" in c)
    assert create < count                                  # pg_restore --schema does not create the schema itself

    proc, _, _ = sandbox(RESTORE, FAKE_LIVE="5", FAKE_RESTORED="0")
    assert proc.returncode == 1 and "is empty" in proc.stderr
    proc, _, _ = sandbox(RESTORE, FAKE_LIVE="5", FAKE_RESTORED="9")
    assert proc.returncode == 1 and "more rows" in proc.stderr


def test_restore_check_never_drops_the_live_database(sandbox):
    sandbox(BACKUP)
    for check_db in ("services", "scratch", "-check"):                  # same as live, or without "check" in the name
        proc, calls, _ = sandbox(RESTORE, CHECK_DB=check_db)
        assert proc.returncode == 2
        assert not any(c.startswith("dropdb") for c in calls)


def test_restore_check_without_dumps_fails(sandbox):
    proc, _, _ = sandbox(RESTORE)
    assert proc.returncode == 1 and "no dumps" in proc.stderr


def test_failure_notice_hides_the_token_from_arguments(sandbox):
    proc, calls, _ = sandbox(NOTIFY, "stenabot.service", NOTIFY_BOT_TOKEN="123:SECRET", OWNER_ID="42")
    assert proc.returncode == 0, proc.stderr
    assert "SECRET" not in " ".join(calls)                    # not in argv, so not in /proc/<pid>/cmdline
    assert "123:SECRET" in sandbox.stdin_file.read_text()     # it arrives via the config on stdin


def test_failure_notice_without_token_only_logs(sandbox):
    proc, calls, _ = sandbox(NOTIFY, "stenabot.service", OWNER_ID="42")
    assert proc.returncode == 0 and "NOTIFY_BOT_TOKEN is not set" in proc.stderr
    assert calls == []


def test_failure_notice_rejects_non_numeric_owner(sandbox):
    proc, calls, _ = sandbox(NOTIFY, "stenabot.service", NOTIFY_BOT_TOKEN="1:x", OWNER_ID="42; rm -rf")
    assert proc.returncode == 2 and calls == []


def test_service_unit_is_hardened_and_matches_the_code():
    unit = UNIT.read_text()
    for required in ("Type=notify", "WatchdogSec=", "RestartPreventExitStatus=3", "NoNewPrivileges=yes",
                     "ProtectSystem=strict", "OnFailure=stenabot-failure@%n.service"):
        assert required in unit, required
    # the unit exits-code contract is defined in code
    from core.auth import EXIT_UNAUTHORIZED
    assert EXIT_UNAUTHORIZED == 3
    watchdog = int(next(line for line in unit.splitlines() if line.startswith("WatchdogSec=")).split("=")[1])
    import config
    assert watchdog > 3 * config.WATCHDOG_SEC          # several missed pings before systemd restarts


def test_scripts_are_executable_and_pass_bash_syntax_check():
    for script in (BACKUP, RESTORE, NOTIFY):
        assert os.access(script, os.X_OK), script
        assert subprocess.run(["bash", "-n", str(script)]).returncode == 0
