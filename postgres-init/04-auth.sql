-- =========================================================================
--  Auth schema — application user accounts (local + Google OAuth).
--  Created idempotently so it can also be re-applied to running databases.
-- =========================================================================
\connect job_db

CREATE SCHEMA IF NOT EXISTS auth;
GRANT ALL PRIVILEGES ON SCHEMA auth TO datauser;

CREATE TABLE IF NOT EXISTS auth.users (
    user_id        BIGSERIAL    PRIMARY KEY,
    email          TEXT         NOT NULL UNIQUE,
    full_name      TEXT         NOT NULL DEFAULT '',
    password_hash  TEXT,                            -- NULL when only OAuth
    provider       TEXT         NOT NULL DEFAULT 'local',  -- 'local' | 'google'
    google_sub     TEXT         UNIQUE,             -- Google account 'sub'
    picture        TEXT,
    created_at     TIMESTAMPTZ  NOT NULL DEFAULT now(),
    last_login_at  TIMESTAMPTZ,
    CONSTRAINT chk_users_provider CHECK (provider IN ('local','google')),
    CONSTRAINT chk_users_password CHECK (
        (provider = 'local'  AND password_hash IS NOT NULL)
     OR (provider = 'google' AND google_sub    IS NOT NULL)
    )
);

CREATE INDEX IF NOT EXISTS idx_users_email      ON auth.users(LOWER(email));
CREATE INDEX IF NOT EXISTS idx_users_google_sub ON auth.users(google_sub) WHERE google_sub IS NOT NULL;

GRANT ALL ON ALL TABLES    IN SCHEMA auth TO datauser;
GRANT ALL ON ALL SEQUENCES IN SCHEMA auth TO datauser;
