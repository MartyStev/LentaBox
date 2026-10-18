CREATE TABLE channel_cursors (
    channel_id TEXT PRIMARY KEY,
    last_message_id BIGINT NOT NULL CHECK (last_message_id >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
