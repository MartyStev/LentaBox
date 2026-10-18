"""The digest queue: written atomically with the post, read in order, marked after sending (real SQL)."""

import pytest

import db.clusters as clusters
import db.digest as digest_db
import db.publications as publications

pytestmark = pytest.mark.integration

CHANNEL = -100500


def entry(headline="Заголовок", link="https://t.me/news/1", label="@news"):
    return {"headline": headline, "link": link, "channel_label": label}


def queue(db, message, **kwargs):
    cluster = clusters.create_cluster([1.0, 0.0])
    claim_id = publications.claim(cluster, CHANNEL, message)
    publications.finalize(claim_id, cluster, CHANNEL, message, f"h{message}", f"text {message}",
                          queue_entry=entry(**kwargs))
    return cluster


def test_finalize_with_queue_entry_writes_post_claim_and_queue_row_together(db):
    cluster = queue(db, 1)
    assert db("SELECT COUNT(*) AS n FROM posts", fetch=True)[0]["n"] == 1
    assert db("SELECT state FROM publication_claims", fetch=True)[0]["state"] == "sent"
    row = digest_db.list_unsent()[0]
    assert (row["cluster_id"], row["channel_id"], row["message_id"]) == (cluster, str(CHANNEL), 1)
    assert (row["headline"], row["link"], row["channel_label"]) == ("Заголовок", "https://t.me/news/1", "@news")


def test_a_failed_finalize_leaves_no_queue_row(db):
    cluster = clusters.create_cluster([1.0, 0.0])
    claim_id = publications.claim(cluster, CHANNEL, 1)
    publications.release(claim_id)                              # the claim is gone: finalize must fail
    with pytest.raises(RuntimeError):
        publications.finalize(claim_id, cluster, CHANNEL, 1, "h", "t", queue_entry=entry())
    assert digest_db.count_unsent() == 0


def test_unsent_rows_come_oldest_first_and_respect_the_limit(db):
    for message in (1, 2, 3):
        queue(db, message, headline=f"news {message}")
    db("UPDATE digest_queue SET created_at = NOW() - INTERVAL '1 hour' WHERE message_id = 3")
    assert [r["headline"] for r in digest_db.list_unsent()] == ["news 3", "news 1", "news 2"]
    assert len(digest_db.list_unsent(limit=2)) == 2
    assert digest_db.count_unsent() == 3


def test_mark_sent_hides_rows_and_records_the_time(db):
    for message in (1, 2):
        queue(db, message)
    assert digest_db.last_sent_at() is None
    ids = [r["id"] for r in digest_db.list_unsent()]

    assert digest_db.mark_sent(ids[:1]) == 1
    assert digest_db.count_unsent() == 1
    assert digest_db.last_sent_at() is not None
    assert digest_db.mark_sent(ids[:1]) == 0                    # already marked
    assert digest_db.mark_sent([]) == 0


def test_purge_removes_only_old_sent_rows(db):
    for message in (1, 2, 3):
        queue(db, message)
    ids = [r["id"] for r in digest_db.list_unsent()]
    digest_db.mark_sent(ids[:2])
    db("UPDATE digest_queue SET sent_at = NOW() - INTERVAL '30 days' WHERE id = %s", (ids[0],))

    assert digest_db.purge_sent(14) == 1
    assert db("SELECT COUNT(*) AS n FROM digest_queue", fetch=True)[0]["n"] == 2
    assert digest_db.count_unsent() == 1


async def test_queue_to_digest_roundtrip_with_real_sql(db):
    from datetime import UTC, datetime
    from types import SimpleNamespace
    from unittest.mock import AsyncMock

    from handlers import maintenance

    queue(db, 1, headline="Первая новость")
    queue(db, 2, headline="Вторая новость", link=None)
    client = SimpleNamespace(send_message=AsyncMock())
    now = datetime(2026, 10, 15, 12, 0, tzinfo=UTC)

    assert await maintenance.digest_once(client, None, now=now) == 2

    text = client.send_message.await_args.args[1]
    assert "Первая новость" in text and "Вторая новость" in text
    assert digest_db.count_unsent() == 0 and digest_db.last_sent_at() is not None
    assert await maintenance.digest_once(client, None, now=now) == 0           # nothing is sent twice
    client.send_message.assert_awaited_once()
