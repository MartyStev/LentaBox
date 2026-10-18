import pytest

from db import migrate

pytestmark = pytest.mark.integration

EXPECTED_TABLES = {
    "channels", "posts", "news_clusters", "publication_claims", "bot_decisions",
    "channel_cursors", "channel_exclusions", "bot_settings", "schema_migrations", "mute_words", "digest_queue",
}


def tables(execute):
    rows = execute(
        "SELECT table_name FROM information_schema.tables WHERE table_schema = current_schema()", fetch=True
    )
    return {r["table_name"] for r in rows}


def test_empty_database_gets_the_full_schema(db):
    assert EXPECTED_TABLES <= tables(db)


def test_every_migration_file_is_recorded_once(db):
    recorded = [r["version"] for r in db("SELECT version FROM schema_migrations ORDER BY version", fetch=True)]
    files = sorted(p.stem for p in migrate.MIGRATION_DIR.glob("[0-9][0-9][0-9]_*.sql"))
    assert recorded == files
    assert recorded[0].startswith("000_")


def test_running_migrations_again_changes_nothing(db):
    migrate.run_migrations()
    count = db("SELECT COUNT(*) AS n FROM schema_migrations", fetch=True)[0]["n"]
    assert count == len(list(migrate.MIGRATION_DIR.glob("[0-9][0-9][0-9]_*.sql")))
