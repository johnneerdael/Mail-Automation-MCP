CREATE TABLE IF NOT EXISTS imap_jobs (
    job_id UUID PRIMARY KEY,
    job_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP NULL,
    finished_at TIMESTAMP NULL,

    total_estimate INT DEFAULT 0,
    processed INT DEFAULT 0,

    cancel_requested BOOLEAN DEFAULT FALSE,
    error TEXT NULL
);

CREATE INDEX IF NOT EXISTS idx_imap_jobs_status_created_at
    ON imap_jobs(status, created_at);

CREATE TABLE IF NOT EXISTS imap_job_events (
    id BIGSERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES imap_jobs(job_id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    level VARCHAR(10) NOT NULL DEFAULT 'info',
    message TEXT NOT NULL,
    data JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_imap_job_events_job_id_id
    ON imap_job_events(job_id, id);
