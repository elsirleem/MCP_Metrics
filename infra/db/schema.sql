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

-- Business Outcomes: Track business metrics to correlate with DORA
CREATE TABLE IF NOT EXISTS business_metrics (
    id SERIAL PRIMARY KEY,
    org_id TEXT NOT NULL DEFAULT 'default',
    date DATE NOT NULL,
    -- Revenue & Growth
    revenue DOUBLE PRECISION,                    -- Daily/weekly revenue
    new_customers INTEGER,                       -- New customer signups
    customer_churn_rate DOUBLE PRECISION,        -- % of customers lost
    -- Customer Experience
    customer_satisfaction_score DOUBLE PRECISION, -- NPS or CSAT (0-100)
    support_tickets INTEGER,                     -- Number of support tickets
    avg_resolution_time_hours DOUBLE PRECISION,  -- Avg time to resolve tickets
    -- Reliability & Incidents
    incidents INTEGER DEFAULT 0,                 -- Production incidents
    incident_severity_avg DOUBLE PRECISION,      -- Avg severity (1-5)
    uptime_percentage DOUBLE PRECISION,          -- Service uptime %
    -- Feature Delivery
    features_shipped INTEGER,                    -- Features delivered
    bug_reports INTEGER,                         -- Bugs reported by users
    -- Custom metrics (flexible JSON)
    custom_metrics JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, date)
);

-- Business-DORA Correlation Cache: Pre-computed correlations
CREATE TABLE IF NOT EXISTS business_correlations (
    id SERIAL PRIMARY KEY,
    org_id TEXT NOT NULL DEFAULT 'default',
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,
    -- Correlation coefficients (-1 to 1)
    df_revenue_corr DOUBLE PRECISION,            -- Deployment Frequency vs Revenue
    df_satisfaction_corr DOUBLE PRECISION,       -- DF vs Customer Satisfaction
    leadtime_revenue_corr DOUBLE PRECISION,      -- Lead Time vs Revenue
    leadtime_satisfaction_corr DOUBLE PRECISION, -- Lead Time vs Satisfaction
    cfr_incidents_corr DOUBLE PRECISION,         -- Change Failure Rate vs Incidents
    cfr_churn_corr DOUBLE PRECISION,             -- CFR vs Customer Churn
    mttr_satisfaction_corr DOUBLE PRECISION,     -- MTTR vs Customer Satisfaction
    mttr_uptime_corr DOUBLE PRECISION,           -- MTTR vs Uptime
    -- Summary insights
    insights JSONB DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(org_id, period_start, period_end)
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
