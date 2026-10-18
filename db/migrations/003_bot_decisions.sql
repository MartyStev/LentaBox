CREATE TABLE IF NOT EXISTS bot_decisions (
    id BIGSERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    channel_id TEXT,
    message_id BIGINT,
    decision TEXT NOT NULL,
    reason TEXT NOT NULL,
    cluster_id BIGINT,
    fuzzy_score DOUBLE PRECISION,
    cluster_score DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_bot_decisions_created_at
ON bot_decisions (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_bot_decisions_message_id
ON bot_decisions (message_id DESC);
