CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL,
    idempotency_key TEXT NOT NULL,
    type TEXT NOT NULL,
    payload JSONB NOT NULL,
    estimated_cost INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (
    status IN (
        'queued',
        'awaiting_approval',
        'running',
        'succeeded',
        'failed',
        'rejected'
        )
    ),
    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL DEFAULT 3,
    leased_by TEXT,
    lease_until TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
     UNIQUE (tenant_id, idempotency_key)
);
CREATE INDEX idx_jobs_status_created_at
ON jobs (status, created_at);