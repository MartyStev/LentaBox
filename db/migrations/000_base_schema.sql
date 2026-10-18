-- Base tables. Everything is IF NOT EXISTS, so on a database that already has them (installs that
-- predate this file) the migration changes nothing and is only recorded. Later migrations add
-- columns (saved_at, origin_key, member_count, source) with ALTER TABLE ... IF NOT EXISTS.

-- One row per story (group of near-identical posts). The embedding is the running centroid.
CREATE TABLE IF NOT EXISTS news_clusters (
    id BIGSERIAL PRIMARY KEY,
    embedding DOUBLE PRECISION[] NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_sent_at TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_news_clusters_created_at ON news_clusters (created_at DESC);

-- Tracked source channels.
CREATE TABLE IF NOT EXISTS channels (
    telegram_id BIGINT PRIMARY KEY,
    username TEXT,
    title TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Posts that were actually published to the target chat.
CREATE TABLE IF NOT EXISTS posts (
    id BIGSERIAL PRIMARY KEY,
    channel_id TEXT NOT NULL,
    telegram_message_id BIGINT NOT NULL,
    text_hash TEXT,
    text_content TEXT,
    cluster_id BIGINT REFERENCES news_clusters (id),
    created_at TIMESTAMP NOT NULL DEFAULT (NOW() AT TIME ZONE 'UTC'),
    UNIQUE (channel_id, telegram_message_id)
);

CREATE INDEX IF NOT EXISTS idx_posts_text_hash ON posts (text_hash) WHERE text_hash IS NOT NULL;
