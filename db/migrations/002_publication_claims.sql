CREATE TABLE IF NOT EXISTS publication_claims (
    id BIGSERIAL PRIMARY KEY,
    cluster_id BIGINT NOT NULL REFERENCES news_clusters(id),
    publication_day DATE NOT NULL DEFAULT CURRENT_DATE,
    channel_id TEXT NOT NULL,
    message_id BIGINT NOT NULL,
    state TEXT NOT NULL DEFAULT 'pending',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sent_at TIMESTAMPTZ,
    UNIQUE (cluster_id, publication_day),
    UNIQUE (channel_id, message_id)
);

CREATE INDEX IF NOT EXISTS idx_publication_claims_pending
ON publication_claims (created_at)
WHERE state = 'pending';
