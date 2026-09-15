/* ============================================================================
   01_schema.sql
   Schema for the Mobile Game Product & Retention Analytics project.
   Target engine: SQLite (portable) / fully compatible with PostgreSQL & MySQL
   with minor type adjustments (see comments).
   ============================================================================ */

DROP TABLE IF EXISTS dim_users;
DROP TABLE IF EXISTS fact_sessions;
DROP TABLE IF EXISTS fact_transactions;
DROP TABLE IF EXISTS ab_test_assignments;

CREATE TABLE dim_users (
    user_id             TEXT PRIMARY KEY,
    install_date        DATE NOT NULL,
    acquisition_channel TEXT NOT NULL,
    country             TEXT NOT NULL,
    device              TEXT NOT NULL,
    ab_group            TEXT NOT NULL CHECK (ab_group IN ('control','treatment'))
);

CREATE TABLE fact_sessions (
    session_id            TEXT PRIMARY KEY,
    user_id                TEXT NOT NULL REFERENCES dim_users(user_id),
    session_date           DATE NOT NULL,
    day_index              INTEGER NOT NULL,       -- days since install (0 = install day)
    session_duration_min   REAL NOT NULL,
    level_reached          INTEGER NOT NULL
);

CREATE TABLE fact_transactions (
    transaction_id      TEXT PRIMARY KEY,
    user_id              TEXT NOT NULL REFERENCES dim_users(user_id),
    transaction_date     DATE NOT NULL,
    sku                  TEXT NOT NULL,
    revenue_usd          REAL NOT NULL
);

CREATE TABLE ab_test_assignments (
    user_id          TEXT NOT NULL REFERENCES dim_users(user_id),
    ab_group          TEXT NOT NULL,
    experiment_name   TEXT NOT NULL,
    assignment_date   DATE NOT NULL
);

CREATE INDEX idx_sessions_user     ON fact_sessions(user_id);
CREATE INDEX idx_sessions_day      ON fact_sessions(day_index);
CREATE INDEX idx_txn_user          ON fact_transactions(user_id);
CREATE INDEX idx_users_install     ON dim_users(install_date);
CREATE INDEX idx_users_ab          ON dim_users(ab_group);
