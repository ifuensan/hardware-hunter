-- 0001_phase1_schema.sql — Phase 1 base schema (AR8 / AR9 / AR10).
--
-- This migration creates the five Phase 1 tables (`_meta`,
-- `wishlist_runtime_state`, `seen_listings`, `alert_snapshots`,
-- `callbacks`) plus the indexes that back FR47 audit queries.
--
-- NFR-S4 (append-only): no UPDATE or DELETE triggers on audit tables.
-- The Store ABC has no mutation methods on audit data, and a unit test
-- enforces that contract. The DB layer is intentionally not the gate.

-- ─────────────────────────────────────────────────────────────────────
-- _meta — schema version + future free-text knobs
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS _meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

-- ─────────────────────────────────────────────────────────────────────
-- wishlist_runtime_state — per-entry mutable state the daemon owns.
-- Snooze + last-poll bookkeeping live here, not in wishlist.yaml.
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS wishlist_runtime_state (
    entry_manufacturer TEXT NOT NULL,
    entry_model        TEXT NOT NULL,
    entry_ref          TEXT NOT NULL,
    snooze_until       TEXT,           -- ISO 8601 UTC, NULL when no snooze
    last_seen_at       TEXT,           -- last time the daemon saw any listing for this entry
    last_alert_at      TEXT,           -- last time we actually fired an alert
    PRIMARY KEY (entry_manufacturer, entry_model, entry_ref)
);

-- ─────────────────────────────────────────────────────────────────────
-- seen_listings — dedup index for FR10. Compound PK across
-- (listing, entry) since one listing can match multiple wishlist
-- entries and we want each pairing acknowledged independently.
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS seen_listings (
    listing_id              TEXT NOT NULL,
    entry_manufacturer      TEXT NOT NULL,
    entry_model             TEXT NOT NULL,
    entry_ref               TEXT NOT NULL,
    url                     TEXT NOT NULL,
    perceptual_photo_hash   TEXT,                -- populated by photo-dedup helper (Story 3.x); NULL until then
    first_seen_at           TEXT NOT NULL,
    last_seen_at            TEXT NOT NULL,
    match_fired             INTEGER NOT NULL DEFAULT 0,  -- 0 = pending/dropped, 1 = alert was sent
    PRIMARY KEY (listing_id, entry_manufacturer, entry_model, entry_ref)
);

CREATE INDEX IF NOT EXISTS idx_seen_listings_entry
    ON seen_listings (entry_manufacturer, entry_model, entry_ref);

CREATE INDEX IF NOT EXISTS idx_seen_listings_last_seen
    ON seen_listings (last_seen_at);

-- ─────────────────────────────────────────────────────────────────────
-- alert_snapshots — the audit table for dispatched alerts (FR47).
-- Carries the JSON-serialized listing + evaluation so the callback
-- handler can replay context for a tap that lands hours later.
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_snapshots (
    audit_id                INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id                TEXT NOT NULL UNIQUE,              -- UUID surfaced in callback_data
    entry_manufacturer      TEXT NOT NULL,
    entry_model             TEXT NOT NULL,
    entry_ref               TEXT NOT NULL,
    entry_display_name      TEXT NOT NULL,
    listing_json            TEXT NOT NULL,                     -- serialized Listing
    evaluation_json         TEXT NOT NULL,                     -- serialized ListingEvaluation
    phase                   TEXT NOT NULL,                     -- "phase1" | "phase2"
    phase2_max_price_eur    TEXT,                              -- Decimal stringified; NULL for Phase 1 alerts
    rendered_at             TEXT NOT NULL                      -- ISO 8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_alert_snapshots_entry
    ON alert_snapshots (entry_manufacturer, entry_model, entry_ref);

CREATE INDEX IF NOT EXISTS idx_alert_snapshots_rendered_at
    ON alert_snapshots (rendered_at);

-- ─────────────────────────────────────────────────────────────────────
-- callbacks — one row per inline-button tap from Telegram. Linked to
-- the originating alert via alert_id (NOT FK at the SQL level — SQLite
-- enforces FKs only when PRAGMA foreign_keys=ON, which we don't enable
-- here; the application is the join authority).
-- ─────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS callbacks (
    audit_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    alert_id              TEXT NOT NULL,
    telegram_message_id   INTEGER NOT NULL,
    chat_id               INTEGER NOT NULL,
    callback_data         TEXT NOT NULL,
    verb                  TEXT NOT NULL,           -- "view" | "skip" | "snooze" | "buy"
    received_at           TEXT NOT NULL            -- ISO 8601 UTC
);

CREATE INDEX IF NOT EXISTS idx_callbacks_alert_id
    ON callbacks (alert_id);

CREATE INDEX IF NOT EXISTS idx_callbacks_received_at
    ON callbacks (received_at);
