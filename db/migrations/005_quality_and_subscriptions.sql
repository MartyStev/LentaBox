-- Источник репоста: "<channel_id>:<message_id>" оригинала (для обычных постов - свой).
ALTER TABLE posts ADD COLUMN IF NOT EXISTS origin_key TEXT;
CREATE INDEX IF NOT EXISTS idx_posts_origin_key
ON posts (origin_key) WHERE origin_key IS NOT NULL;

-- Короткая выдержка текста для решений (в том числе skip): нужна для разметки и подбора порога.
ALTER TABLE bot_decisions ADD COLUMN IF NOT EXISTS excerpt TEXT;

-- Кластер хранит центроид: сколько постов в него уже вошло.
ALTER TABLE news_clusters ADD COLUMN IF NOT EXISTS member_count INTEGER NOT NULL DEFAULT 1;

-- Откуда появился канал: manual (/add) или sync (из подписок аккаунта).
-- Автосинхронизация удаляет только каналы с source = 'sync'.
ALTER TABLE channels ADD COLUMN IF NOT EXISTS source TEXT NOT NULL DEFAULT 'manual';

-- Каналы, которые владелец явно отключил: автосинхронизация их не возвращает.
CREATE TABLE IF NOT EXISTS channel_exclusions (
    channel_id BIGINT PRIMARY KEY,
    excluded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Настройки, меняемые командами без перезапуска.
CREATE TABLE IF NOT EXISTS bot_settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
