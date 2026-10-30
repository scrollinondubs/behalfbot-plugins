-- 002_dating_swipes.sql -- swipe review store behind the dating dashboard tab.
--
-- Run:
--   psql "$BEHALFBOT_PG_DSN" -f 002_dating_swipes.sql
--
-- Idempotent via IF NOT EXISTS on all CREATE statements.
--
-- Tables:
--   dating_profiles       -- one row per profile screenshot the agent encountered,
--                            keyed on the screenshot basename (name+age is not unique).
--                            agent_action is the swipe the agent made.
--   dating_reviews        -- the installer's bucket call per review event. Latest row
--                            per profile wins; history keeps corrections auditable.
--   dating_recovery_queue -- the "lost list": false negatives (agent passed, installer
--                            liked) awaiting a re-like when the profile resurfaces.
--
-- No embedding column: the dashboard never reads one, and it would make pgvector a
-- hard dependency of the plugin. Add it in a later migration with the matcher.

BEGIN;

CREATE TABLE IF NOT EXISTS dating_profiles (
    id                  BIGSERIAL PRIMARY KEY,
    screenshot_basename TEXT NOT NULL UNIQUE,
    screenshot_path     TEXT,
    name                TEXT NOT NULL,
    age                 INTEGER,
    platform            TEXT NOT NULL,
    encountered_on      DATE,
    agent_action        TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_dating_profiles_name_platform
    ON dating_profiles (name, platform);

CREATE TABLE IF NOT EXISTS dating_reviews (
    id               BIGSERIAL PRIMARY KEY,
    profile_id       BIGINT NOT NULL REFERENCES dating_profiles(id) ON DELETE CASCADE,
    installer_bucket TEXT NOT NULL CHECK (installer_bucket IN ('like', 'super-like', 'pass', 'no-opinion')),
    outcome          TEXT CHECK (outcome IN ('tp', 'tn', 'fp', 'fn', 'no_opinion')),
    source           TEXT NOT NULL DEFAULT 'dashboard'
                     CHECK (source IN ('dashboard', 'desktop-reconcile', 'jsonl-backfill')),
    reviewed_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_dating_reviews_profile
    ON dating_reviews (profile_id, reviewed_at DESC);

CREATE TABLE IF NOT EXISTS dating_recovery_queue (
    id           BIGSERIAL PRIMARY KEY,
    profile_id   BIGINT NOT NULL UNIQUE REFERENCES dating_profiles(id) ON DELETE CASCADE,
    status       TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'recovered', 'lost')),
    added_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recovered_at TIMESTAMPTZ,
    match_method TEXT,
    notes        TEXT
);

CREATE INDEX IF NOT EXISTS ix_dating_recovery_status
    ON dating_recovery_queue (status);

COMMIT;
