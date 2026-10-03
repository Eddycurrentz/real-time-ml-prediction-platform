CREATE TABLE IF NOT EXISTS raw_transactions (
    transaction_id UUID PRIMARY KEY,
    payload JSONB NOT NULL,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS customer_state (
    customer_id TEXT PRIMARY KEY,
    last_location TEXT,
    last_device_type TEXT,
    last_ts TIMESTAMPTZ,
    amount_mean DOUBLE PRECISION,
    amount_std DOUBLE PRECISION,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS dlq_events (
    id SERIAL PRIMARY KEY,
    transaction_id TEXT,
    reason TEXT NOT NULL,
    payload JSONB,
    topic TEXT,
    offset BIGINT,
    received_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_raw_transactions_received_at
    ON raw_transactions (received_at);

CREATE INDEX IF NOT EXISTS idx_dlq_events_received_at
    ON dlq_events (received_at);
