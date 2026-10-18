#!/usr/bin/env bash
# Backup of the stenabot schema: pg_dump to a compressed file, KEEP_DAYS kept locally, optional copy to another host.
# Install on the PostgreSQL host together with stenabot-backup.service and stenabot-backup.timer.
# Settings live in /etc/stenabot-backup.env: PGDATABASE, PGUSER (read access to the schema), SCHEMA (default stenabot),
# BACKUP_DIR, KEEP_DAYS, OFFSITE (rsync destination like host:/path/ or user@host:/path/; empty = no copy),
# OFFSITE_KEEP_DAYS (pruned there over ssh).
# No --delete (losing the local directory must not wipe the offsite copy), dumps are mode 600, contents are checked.
set -euo pipefail
umask 077
: "${PGDATABASE:?}" "${SCHEMA:=stenabot}" "${BACKUP_DIR:=/var/backups/stenabot}" "${KEEP_DAYS:=14}" "${OFFSITE:=}" "${OFFSITE_KEEP_DAYS:=60}"
[[ "$KEEP_DAYS" =~ ^[0-9]+$ && "$OFFSITE_KEEP_DAYS" =~ ^[0-9]+$ ]] || { echo "KEEP_DAYS and OFFSITE_KEEP_DAYS must be numbers" >&2; exit 2; }
[[ "$SCHEMA" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "SCHEMA must be a plain identifier" >&2; exit 2; }
mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%d-%H%M)
file="$BACKUP_DIR/stenabot-$stamp.dump"
previous=$(ls -1t "$BACKUP_DIR"/stenabot-*.dump 2>/dev/null | head -1 || true)
pg_dump --format=custom --compress=6 --schema="$SCHEMA" --file="$file" "$PGDATABASE"
listing=$(pg_restore --list "$file")                       # a variable, not grep -q through a pipe: SIGPIPE under pipefail
grep -q "TABLE DATA $SCHEMA posts" <<<"$listing" || { echo "backup $file has no posts data" >&2; exit 1; }
if [[ -n "$previous" && -s "$previous" ]]; then
    new_size=$(wc -c <"$file"); old_size=$(wc -c <"$previous")       # wc, not stat -c: portable
    if (( new_size * 2 < old_size )); then
        echo "backup suspicious: $file ($new_size bytes) is less than half of $previous ($old_size bytes)" >&2
        exit 1                                                  # the file stays, OnFailure notifies
    fi
fi
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'stenabot-*.dump' -mtime +"$KEEP_DAYS" -delete
if [[ -n "$OFFSITE" ]]; then
    # validate before rsync: a value like "-oProxyCommand=..." would otherwise be parsed as an rsync option
    [[ "$OFFSITE" != -* ]] || { echo "OFFSITE: value cannot start with '-'" >&2; exit 2; }
    remote=
    if [[ "$OFFSITE" == *:* && "$OFFSITE" != *::* ]]; then
        host="${OFFSITE%%:*}"; remote_dir="${OFFSITE#*:}"
        [[ "$remote_dir" =~ ^[/~][A-Za-z0-9_./~-]*$ ]] || { echo "OFFSITE: remote path must be absolute (or ~) and have no odd characters" >&2; exit 2; }
        [[ "$host" != -* ]] || { echo "OFFSITE: host cannot start with '-'" >&2; exit 2; }
        remote=1
    fi
    rsync -a -- "$BACKUP_DIR"/ "$OFFSITE"
    if [[ -n "$remote" ]]; then
        # a failed prune fails the unit: otherwise the retention on the remote host silently stops
        ssh -- "$host" "find $remote_dir -maxdepth 1 -type f -name 'stenabot-*.dump' -mtime +${OFFSITE_KEEP_DAYS} -delete"
    fi
fi
echo "backup ok: $file ($(du -h "$file" | cut -f1))"
