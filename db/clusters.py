from db.connection import execute


def create_cluster(embedding):
    rows = execute(
        """
        INSERT INTO news_clusters (embedding, member_count)
        VALUES (%s, 1)
        RETURNING id
        """,
        (embedding,),
        fetch=True,
        retry=False,
    )

    if not rows:
        raise RuntimeError("Failed to create cluster")

    return rows[0]["id"]


def get_recent_clusters(hours=72, limit=200):
    """
    Return clusters worth comparing against:
    [(cluster_id, centroid, member_count), ...]
    """
    rows = execute(
        """
        SELECT id, embedding, member_count
        FROM news_clusters
        WHERE created_at >= NOW() - (%s * INTERVAL '1 hour')
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (hours, limit),
        fetch=True
    )

    return [(r["id"], r["embedding"], r["member_count"]) for r in rows] if rows else []


def update_centroid(cluster_id, centroid, member_count):
    execute(
        """
        UPDATE news_clusters
        SET embedding = %s, member_count = %s, updated_at = NOW()
        WHERE id = %s
        """,
        (centroid, member_count, cluster_id),
    )
