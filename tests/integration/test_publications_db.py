"""Exactly-once publishing: claims, finalisation, manual resolution, expiry (real SQL)."""

import pytest

import db.channels as channels
import db.clusters as clusters
import db.publications as publications

pytestmark = pytest.mark.integration

CHANNEL = -100500


@pytest.fixture
def cluster(db):
    return clusters.create_cluster([1.0, 0.0])


def state(db, claim_id):
    return db("SELECT state FROM publication_claims WHERE id = %s", (claim_id,), fetch=True)[0]["state"]


def test_second_claim_for_the_same_story_is_refused(db, cluster):
    first = publications.claim(cluster, CHANNEL, 1)
    assert first is not None
    assert publications.claim(cluster, -100501, 9) is None


def test_the_same_message_cannot_be_claimed_for_another_story(db, cluster):
    other = clusters.create_cluster([0.0, 1.0])
    assert publications.claim(cluster, CHANNEL, 1) is not None
    assert publications.claim(other, CHANNEL, 1) is None


def test_cluster_sent_before_claims_existed_is_still_protected(db, cluster):
    """Legacy rows: last_sent_at is set but there is no claim for it."""
    db("UPDATE news_clusters SET last_sent_at = NOW() - INTERVAL '1 hour' WHERE id = %s", (cluster,))
    assert publications.claim(cluster, CHANNEL, 1) is None


def test_finalize_saves_post_stamps_cluster_and_closes_claim(db, cluster):
    claim_id = publications.claim(cluster, CHANNEL, 7)
    publications.finalize(claim_id, cluster, CHANNEL, 7, "hash", "Текст новости", origin_key=f"{CHANNEL}:7")

    post = db("SELECT * FROM posts", fetch=True)[0]
    assert (post["channel_id"], post["telegram_message_id"], post["text_content"]) == (str(CHANNEL), 7, "Текст новости")
    assert post["saved_at"] is not None
    assert db("SELECT last_sent_at FROM news_clusters WHERE id = %s", (cluster,), fetch=True)[0]["last_sent_at"]
    assert state(db, claim_id) == "sent"
    assert publications.claim(cluster, -100501, 8) is None


def test_finalize_of_a_closed_claim_rolls_everything_back(db, cluster):
    claim_id = publications.claim(cluster, CHANNEL, 7)
    publications.release(claim_id)
    with pytest.raises(RuntimeError):
        publications.finalize(claim_id, cluster, CHANNEL, 7, "hash", "text")
    assert db("SELECT COUNT(*) AS n FROM posts", fetch=True)[0]["n"] == 0
    assert db("SELECT last_sent_at FROM news_clusters WHERE id = %s", (cluster,), fetch=True)[0]["last_sent_at"] is None


def test_story_can_be_published_again_after_the_window(db, cluster):
    claim_id = publications.claim(cluster, CHANNEL, 7)
    publications.finalize(claim_id, cluster, CHANNEL, 7, "h", "t")
    db("UPDATE news_clusters SET last_sent_at = NOW() - INTERVAL '2 days' WHERE id = %s", (cluster,))
    db("UPDATE publication_claims SET created_at = NOW() - INTERVAL '2 days', publication_day = CURRENT_DATE - 2")
    assert publications.claim(cluster, -100501, 99) is not None


def test_release_drops_only_pending_claims(db, cluster):
    pending = publications.claim(cluster, CHANNEL, 1)
    publications.release(pending)
    assert db("SELECT COUNT(*) AS n FROM publication_claims", fetch=True)[0]["n"] == 0

    sent = publications.claim(cluster, CHANNEL, 2)
    publications.finalize(sent, cluster, CHANNEL, 2, "h", "t")
    publications.release(sent)
    assert state(db, sent) == "sent"


def test_pending_claim_blocks_neighbours_and_is_listed(db, cluster):
    channels.add_channel(CHANNEL, "news", "News")
    claim_id = publications.claim(cluster, CHANNEL, 5)
    assert publications.has_pending_conflict(cluster, CHANNEL, 6)
    assert publications.has_pending_conflict(clusters.create_cluster([0.0, 1.0]), CHANNEL, 5)
    assert not publications.has_pending_conflict(clusters.create_cluster([0.5, 0.5]), CHANNEL, 6)

    listed = publications.list_pending()
    assert [(r["id"], r["username"], r["title"]) for r in listed] == [(claim_id, "news", "News")]
    assert publications.get_pending(claim_id)["message_id"] == 5
    assert publications.get_pending(claim_id + 1000) is None


def test_resolve_sent_stamps_the_cluster_and_keeps_the_claim(db, cluster):
    claim_id = publications.claim(cluster, CHANNEL, 5)
    assert publications.resolve_pending(claim_id, "sent") is True
    assert state(db, claim_id) == "sent"
    assert db("SELECT last_sent_at FROM news_clusters WHERE id = %s", (cluster,), fetch=True)[0]["last_sent_at"]
    assert publications.resolve_pending(claim_id, "sent") is False        # already closed


def test_resolve_failed_deletes_the_claim_so_the_send_is_retried(db, cluster):
    claim_id = publications.claim(cluster, CHANNEL, 5)
    assert publications.resolve_pending(claim_id, "failed") is True
    assert publications.claim(cluster, CHANNEL, 5) is not None


def test_resolve_rejects_unknown_outcome(db):
    with pytest.raises(ValueError):
        publications.resolve_pending(1, "maybe")


def test_expire_pending_closes_only_old_claims(db, cluster):
    channels.add_channel(CHANNEL, "news", "News")
    old = publications.claim(cluster, CHANNEL, 1)
    fresh = publications.claim(clusters.create_cluster([0.0, 1.0]), CHANNEL, 2)
    db("UPDATE publication_claims SET created_at = NOW() - INTERVAL '30 hours' WHERE id = %s", (old,))

    expired = publications.expire_pending(24)

    assert [r["id"] for r in expired] == [old]
    assert expired[0]["username"] == "news"
    assert state(db, old) == "expired"
    assert state(db, fresh) == "pending"
    assert publications.expire_pending(24) == []
