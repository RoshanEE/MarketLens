-- MarketLens initial schema migration
-- Run this in Supabase SQL editor or via supabase db push

-- Research runs: one per user research session
CREATE TABLE IF NOT EXISTS ml_research_runs (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID NOT NULL REFERENCES auth.users(id) ON DELETE CASCADE,
    title           TEXT,
    competitors     TEXT[]          NOT NULL DEFAULT '{}',
    topics          TEXT[]          NOT NULL DEFAULT '{}',
    context         TEXT,
    status          TEXT            NOT NULL DEFAULT 'pending',
    error           TEXT,
    content_hashes  JSONB           NOT NULL DEFAULT '{}',
    created_at      TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    completed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_runs_user_id ON ml_research_runs(user_id);
CREATE INDEX IF NOT EXISTS idx_runs_status  ON ml_research_runs(status);

-- Source URLs associated with a run
CREATE TABLE IF NOT EXISTS ml_source_urls (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id           UUID NOT NULL REFERENCES ml_research_runs(id) ON DELETE CASCADE,
    url              TEXT NOT NULL,
    page_title       TEXT,
    crawled_content  TEXT,
    content_hash     TEXT,
    crawl_status     TEXT NOT NULL DEFAULT 'pending',
    error            TEXT,
    crawled_at       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_source_urls_run_id ON ml_source_urls(run_id);

-- Generated intelligence reports
CREATE TABLE IF NOT EXISTS ml_reports (
    id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                UUID UNIQUE NOT NULL REFERENCES ml_research_runs(id) ON DELETE CASCADE,
    themes                JSONB NOT NULL DEFAULT '[]',
    competitor_activities JSONB NOT NULL DEFAULT '[]',
    key_insights          JSONB NOT NULL DEFAULT '[]',
    hallucination_results JSONB NOT NULL DEFAULT '{}',
    overall_confidence    FLOAT,
    changes_detected      JSONB NOT NULL DEFAULT '[]',
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Row-Level Security: users can only access their own data
ALTER TABLE ml_research_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE ml_source_urls   ENABLE ROW LEVEL SECURITY;
ALTER TABLE ml_reports       ENABLE ROW LEVEL SECURITY;

-- Runs policy
DO $$ BEGIN
  CREATE POLICY "users_own_runs" ON ml_research_runs
      USING (auth.uid() = user_id);
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Source URLs policy (inherits via run ownership)
DO $$ BEGIN
  CREATE POLICY "users_own_source_urls" ON ml_source_urls
      USING (
          run_id IN (SELECT id FROM ml_research_runs WHERE user_id = auth.uid())
      );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- Reports policy
DO $$ BEGIN
  CREATE POLICY "users_own_reports" ON ml_reports
      USING (
          run_id IN (SELECT id FROM ml_research_runs WHERE user_id = auth.uid())
      );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
