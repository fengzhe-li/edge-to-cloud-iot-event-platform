-- Apply explicitly to an existing deployment before enabling the new ingest handler.
-- Durable retry ledger; no automatic expiry. Existing history is not backfilled.
CREATE TABLE IF NOT EXISTS public.ingested_events (
    event_key text PRIMARY KEY,
    payload_hash text NOT NULL,
    processed_at timestamptz NOT NULL DEFAULT now()
);
