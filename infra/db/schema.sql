-- Core schema for metrics and insights
CREATE TABLE IF NOT EXISTS dora_metrics (
    id SERIAL PRIMARY KEY,
    repo_id TEXT NOT NULL,
    date DATE NOT NULL,
    deployment_frequency INTEGER DEFAULT 0,
    avg_lead_time_minutes DOUBLE PRECISION DEFAULT 0,
    change_failure_rate DOUBLE PRECISION DEFAULT 0,
    mttr_minutes DOUBLE PRECISION DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(repo_id, date)
);

CREATE TABLE IF NOT EXISTS daily_insights (
    id SERIAL PRIMARY KEY,
    repo_id TEXT NOT NULL,
    date DATE NOT NULL,
    summary_text TEXT,
    risk_flags JSONB DEFAULT '[]'::jsonb,
    top_contributors JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(repo_id, date)
);

-- Optional: track ingestion runs
CREATE TABLE IF NOT EXISTS job_runs (
    id SERIAL PRIMARY KEY,
    job_name TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    details JSONB
);
