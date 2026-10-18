"""Posts, clusters, channels, cursors, settings, decisions and the instance lock (real SQL)."""

import pytest

import db.channels as channels
import db.clusters as clusters
import db.cursors as cursors
import db.instance_lock as instance_lock
import db.metrics as metrics
import db.posts as posts
import db.publications as publications
import db.settings as settings_db

pytestmark = pytest.mark.integration


def publish(db, text, *, channel=-1001, message=1, text_hash="h", origin=None):
    cluster = clusters.create_cluster([1.0, 0.0])
    claim_id = publications.claim(cluster, channel, message)
    publications.finalize(claim_id, cluster, channel, message, text_hash, text, origin)
    return cluster


def test_posts_exact_origin_and_recent_texts(db):
    assert posts.last_saved_at() is None
    publish(db, "первая", message=1, text_hash="aaa", origin="-1:1")
    publish(db, "вторая", message=2, text_hash="bbb")

    assert posts.post_exists("aaa") and not posts.post_exists("zzz")
    assert posts.origin_seen("-1:1") and not posts.origin_seen("-1:2")
    assert posts.get_recent_texts(10) == ["вторая", "первая"]
    assert posts.post_exists("aaa", limit=1) is False          # outside the "recent" window
    assert posts.last_saved_at() is not None


def test_clusters_recent_and_centroid_update(db):
    first = clusters.create_cluster([1.0, 0.0])
    clusters.update_centroid(first, [0.5, 0.5], 3)
    old = clusters.create_cluster([0.0, 1.0])
    db("UPDATE news_clusters SET created_at = NOW() - INTERVAL '100 hours' WHERE id = %s", (old,))

    recent = clusters.get_recent_clusters(hours=48, limit=10)

    assert recent == [(first, [0.5, 0.5], 3)]
    assert [c[0] for c in clusters.get_recent_clusters(hours=200, limit=10)] == [first, old]
    assert len(clusters.get_recent_clusters(hours=200, limit=1)) == 1


def test_manual_add_upgrades_a_synced_channel_but_sync_never_downgrades(db):
    channels.add_channel(1, "a", "A", source="sync")
    channels.add_channel(1, "a", "A", source="manual")
    assert channels.list_channels()[0]["source"] == "manual"
    channels.add_channel(1, "a", "A", source="sync")
    assert channels.list_channels()[0]["source"] == "manual"


def test_remove_channel_drops_its_cursor_and_exclusions_roundtrip(db):
    channels.add_channel(7, "seven", "Seven")
    cursors.initialize(7, 100)
    channels.remove_channel(7)
    assert channels.list_channels() == [] and cursors.get(7) is None

    channels.add_exclusion(7)
    channels.add_exclusion(7)
    assert channels.list_exclusions() == {7}
    channels.clear_exclusion(7)
    assert channels.list_exclusions() == set()


def test_channels_are_sorted_by_title_with_untitled_last(db):
    channels.add_channel(1, None, None)
    channels.add_channel(2, "b", "Beta")
    channels.add_channel(3, "a", "Alpha")
    assert [c["telegram_id"] for c in channels.list_channels()] == [3, 2, 1]


def test_cursor_only_moves_forward(db):
    assert cursors.get(5) is None
    cursors.initialize(5, 10)
    cursors.initialize(5, 99)            # second initialisation is ignored
    cursors.advance(5, 20)
    cursors.advance(5, 15)               # going back is ignored
    assert cursors.get(5) == 20
    assert [(r["channel_id"], r["last_message_id"]) for r in cursors.list_all()] == [("5", 20)]


def test_settings_roundtrip(db):
    assert settings_db.load_all() == {}
    settings_db.save("cluster_threshold", 0.9)
    settings_db.save("cluster_threshold", 0.95)
    settings_db.save("autosync", True)
    assert settings_db.load_all() == {"cluster_threshold": "0.95", "autosync": "True"}
    settings_db.delete("autosync")
    assert set(settings_db.load_all()) == {"cluster_threshold"}


def test_decisions_dedup_stats_and_why(db):
    channels.add_channel(-1001, "news", "News")
    metrics.log_decision(-1001, 5, "skip", "advertisement", excerpt="реклама")
    metrics.log_decision(-1001, 5, "skip", "advertisement", excerpt="реклама")     # same decision within an hour
    metrics.log_decision(-1001, 5, "sent", "published", cluster_id=None, fuzzy_score=10.5, cluster_score=0.4)
    metrics.log_decision(-1002, 6, "skip", "too_short")

    totals, reasons = metrics.get_stats_last_hours(24)
    assert (totals["total"], totals["sent"], totals["skipped"]) == (3, 1, 2)
    assert {r["reason"]: r["cnt"] for r in reasons} == {"advertisement": 1, "published": 1, "too_short": 1}

    why = metrics.get_why_by_message_id(5)
    assert {w["reason"] for w in why} == {"advertisement", "published"}
    assert metrics.get_sent_counts(24) == {"-1001": 1}

    by_channel = {r["channel_id"]: r for r in metrics.get_channel_stats(24)}
    assert by_channel["-1001"]["title"] == "News" and by_channel["-1001"]["sent"] == 1
    assert by_channel["-1002"]["title"] is None


def test_purge_deletes_old_decisions_in_batches(db):
    for message in range(5):
        metrics.log_decision(-1001, message, "skip", "too_short")
    db("UPDATE bot_decisions SET created_at = NOW() - INTERVAL '100 days' WHERE message_id < 3")

    assert metrics.purge_old_decisions(90, batch=2) == 3
    assert db("SELECT COUNT(*) AS n FROM bot_decisions", fetch=True)[0]["n"] == 2
    assert metrics.purge_old_decisions(90, batch=2) == 0


def test_only_one_instance_may_hold_the_lock(db, monkeypatch):
    monkeypatch.setattr(instance_lock, "_lock_connection", None)
    assert instance_lock.still_held() is False
    assert instance_lock.acquire() is True
    assert instance_lock.still_held() is True
    held = instance_lock._lock_connection
    monkeypatch.setattr(instance_lock, "_lock_connection", None)
    try:
        assert instance_lock.acquire() is False             # another session cannot take it
    finally:
        held.close()


def test_queued_stories_are_counted_separately_and_as_published_per_channel(db):
    metrics.log_decision(-1001, 1, "sent", "published")
    metrics.log_decision(-1001, 2, "queued", "digest")
    metrics.log_decision(-1001, 3, "queued", "quiet_hours")
    metrics.log_decision(-1001, 4, "skip", "too_short")

    totals, _ = metrics.get_stats_last_hours(24)
    assert (totals["total"], totals["sent"], totals["queued"], totals["skipped"]) == (4, 1, 2, 1)
    assert metrics.get_sent_counts(24) == {"-1001": 3}           # published now or queued for the digest
    row = metrics.get_channel_stats(24)[0]
    assert (row["sent"], row["queued"], row["skipped"]) == (1, 2, 1)
