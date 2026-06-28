-- Add source_run_id to track which run a rerun originated from.
-- Used for change detection: compare crawled content against the specific
-- run that was rerun rather than across all previous runs.

ALTER TABLE ml_research_runs
  ADD COLUMN IF NOT EXISTS source_run_id UUID
    REFERENCES ml_research_runs(id) ON DELETE SET NULL;
