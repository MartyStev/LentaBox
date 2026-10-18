#!/usr/bin/env bash
# Restore check: the latest dump is restored into a throwaway database and row counts are compared with the live
# schema. Run monthly from stenabot-restore-check.timer on the PostgreSQL host; on mismatch or error exit 1 + OnFailure.
set -euo pipefail
: "${PGDATABASE:?}" "${SCHEMA:=stenabot}" "${BACKUP_DIR:=/var/backups/stenabot}" "${CHECK_DB:=stenabot_check}"
[[ "$SCHEMA" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || { echo "SCHEMA must be a plain identifier" >&2; exit 2; }
# dropdb below erases CHECK_DB: it must never coincide with the live database, whatever the env file says
[[ "$CHECK_DB" =~ ^[A-Za-z_][A-Za-z0-9_]*$ && "$CHECK_DB" != "$PGDATABASE" && "$CHECK_DB" == *check* ]] || { echo "CHECK_DB ($CHECK_DB) must differ from PGDATABASE and contain 'check'" >&2; exit 2; }
latest=$(ls -1t "$BACKUP_DIR"/stenabot-*.dump 2>/dev/null | head -1 || true)
[[ -n "$latest" ]] || { echo "no dumps in $BACKUP_DIR" >&2; exit 1; }
dropdb --if-exists "$CHECK_DB"
createdb "$CHECK_DB"
trap 'dropdb --if-exists "$CHECK_DB"' EXIT
# pg_dump --schema does not put CREATE SCHEMA into the archive, so create it first
psql -qAtc "CREATE SCHEMA $SCHEMA" "$CHECK_DB"
pg_restore --dbname "$CHECK_DB" --schema "$SCHEMA" --no-owner --exit-on-error "$latest"
for table in posts channels publication_claims; do
    live=$(psql -Atqc "SELECT COUNT(*) FROM $SCHEMA.$table" "$PGDATABASE")
    restored=$(psql -Atqc "SELECT COUNT(*) FROM $SCHEMA.$table" "$CHECK_DB")
    echo "$table: live $live, restored $restored"
    if (( restored > live )); then echo "restored $table has more rows than live" >&2; exit 1; fi
    if (( live > 0 && restored == 0 )); then echo "restored $table is empty" >&2; exit 1; fi
done
echo "restore check ok: $latest"
