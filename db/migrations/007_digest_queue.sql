-- Stories waiting for a digest message (delivery mode "digest" or quiet hours).
-- A row is written in the same transaction that records the post, so the story counts as published for
-- deduplication from that moment; sent_at is set after the digest message reaches the target chat.
CREATE TABLE IF NOT EXISTS digest_queue (
    id BIGSERIAL PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES news_clusters (id),
    channel_id TEXT NOT NULL,
    message_id BIGINT NOT NULL,
    headline TEXT NOT NULL,
    link TEXT,
    channel_label TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    UNIQUE (channel_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_digest_queue_unsent ON digest_queue (created_at) WHERE sent_at IS NULL;
