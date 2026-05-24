-- =============================================================================
-- URL Shortener - MySQL Database Schema
-- =============================================================================
-- This file is for manual MySQL setup. When using SQLAlchemy with SQLite
-- (local dev), tables are created automatically via db.init_db().
--
-- Usage:
--   mysql -u root -p your_database < schema.sql
-- =============================================================================

CREATE TABLE IF NOT EXISTS urls (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    short_id    VARCHAR(30)  NOT NULL,
    original_url TEXT        NOT NULL,
    click_count INT          NOT NULL DEFAULT 0,
    created_at  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP,

    -- Unique constraint ensures no duplicate short IDs
    CONSTRAINT uq_short_id UNIQUE (short_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Index for fast lookups during redirection (the hot path)
CREATE INDEX idx_short_id ON urls (short_id);

-- Index for the stats page which sorts by click_count DESC
CREATE INDEX idx_click_count ON urls (click_count DESC);
