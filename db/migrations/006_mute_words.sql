-- Words the owner muted with /mute: a post containing any of them is skipped (reason "muted").
CREATE TABLE IF NOT EXISTS mute_words (
    word TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
