# MarketLens — Database Design

## Why Supabase

Supabase is a managed Postgres platform that bundles:

- **Hosted PostgreSQL** — no database server to provision or maintain
- **Auth** — JWT-based user management that integrates directly with DB-level Row-Level Security
- **Row-Level Security** — Postgres RLS policies ensure users can only access their own rows, enforced at the database engine layer (not just in application code)
- **SDK** — a Python and JavaScript client that handles connection pooling, auth, and real-time subscriptions

For a project like MarketLens the combination is compelling: a production-grade relational database, user auth, and data isolation are all available on the free tier without managing infrastructure. The alternative — spinning up RDS, writing auth middleware, and building token management — would be significant undifferentiated work.

---

## Data Model

```
auth.users  (Supabase managed)
      │
      │  user_id FK
      ▼
ml_research_runs  ──────────────────────────────────────────── self-ref (source_run_id)
      │
      │  run_id FK
      ├──────────────────────────────────────────────────────────────────────
      │                                                                     │
      ▼  (1-to-many)                                              ▼  (1-to-1)
ml_source_urls                                               ml_reports
```

### `ml_research_runs`

The core entity — one row per research job.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | auto-generated |
| `user_id` | UUID FK | references `auth.users` — RLS key |
| `title` | TEXT | auto-generated from competitors/topics if not provided |
| `competitors` | TEXT[] | list of competitor names to track |
| `topics` | TEXT[] | list of research topics |
| `context` | TEXT | optional free-text context for the LLM |
| `status` | TEXT | `pending` → `crawling` → `analyzing` → `judging` → `complete` / `failed` |
| `error` | TEXT | user-friendly error message if `status = failed` |
| `source_run_id` | UUID FK (self-ref, nullable) | points to the run this was re-run from; `SET NULL` on delete |
| `content_hashes` | JSONB | `{ url: sha256_hash }` — stored after completion for future change detection |
| `created_at` | TIMESTAMPTZ | |
| `completed_at` | TIMESTAMPTZ | set when status becomes `complete` or `failed` |

**Why `source_run_id`?**
When a user re-runs a report, we need to know which specific previous run to compare content hashes against. A self-referential FK is the simplest reliable approach — it's explicit, survives deletions gracefully (`SET NULL`), and avoids the ambiguity of "compare against most recent run by the same user with the same URLs."

**Why `content_hashes` JSONB on the run?**
Storing `{ url → hash }` on the run row means future re-runs can fetch the entire hash map in a single scalar query. The alternative — joining to `ml_source_urls` and aggregating hashes at query time — is more expensive and adds a join to the already-complex pipeline.

---

### `ml_source_urls`

One row per URL per run.

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `run_id` | UUID FK | references `ml_research_runs` — cascade delete |
| `url` | TEXT | the URL as submitted by the user |
| `page_title` | TEXT | extracted by crawler |
| `crawled_content` | TEXT | full extracted text (used by judge, stored for audit) |
| `content_hash` | TEXT | SHA-256 of `crawled_content` |
| `crawl_status` | TEXT | `pending` → `success` / `failed` |
| `error` | TEXT | crawl error message if `crawl_status = failed` |
| `crawled_at` | TIMESTAMPTZ | |

**Why store `crawled_content`?**
The judge service needs to verify each claim against its source. Storing the full crawled text means the judge has access to the exact content the analysis was based on — no second crawl needed, no risk of page content having changed by verification time. The tradeoff is storage size, which is acceptable given the bounded number of URLs per run.

---

### `ml_reports`

One row per completed run (1-to-1 with `ml_research_runs`).

| Column | Type | Notes |
|---|---|---|
| `id` | UUID PK | |
| `run_id` | UUID FK (unique) | references `ml_research_runs` |
| `themes` | JSONB | list of theme objects with insights |
| `competitor_activities` | JSONB | per-competitor activity lists |
| `key_insights` | JSONB | top-level cross-source insights |
| `hallucination_results` | JSONB | `{ total_claims, verified_claims, unverified_claims, overall_confidence, confidence_threshold }` |
| `overall_confidence` | FLOAT | stored separately for fast list-view queries without parsing JSONB |
| `changes_detected` | JSONB | `[ { url, type: "new_url" | "content_changed" | "url_removed" } ]` |
| `created_at` | TIMESTAMPTZ | |

**Why JSONB for report content?**
The report structure (themes, insights, competitor activities) is deeply nested and may evolve as the AI prompts and output formats change. JSONB avoids needing a schema migration every time the report shape changes. Postgres JSONB is still fully queryable with `->` and `@>` operators if needed.

**Why `overall_confidence` as a separate column?**
The dashboard list view needs to display confidence scores for all runs without fetching the full JSONB blobs. A separate float column allows a single efficient query (the list endpoint uses a LEFT JOIN to `ml_reports` selecting only `overall_confidence` and `hallucination_results`).

---

## Row-Level Security

All three tables have RLS enabled. Policies:

```sql
-- Users can only read/write their own runs
CREATE POLICY "users_own_runs" ON ml_research_runs
    USING (auth.uid() = user_id);

-- Source URLs are accessible if the user owns the parent run
CREATE POLICY "users_own_source_urls" ON ml_source_urls
    USING (
        EXISTS (
            SELECT 1 FROM ml_research_runs r
            WHERE r.id = ml_source_urls.run_id
              AND r.user_id = auth.uid()
        )
    );

-- Reports are accessible if the user owns the parent run
CREATE POLICY "users_own_reports" ON ml_reports
    USING (
        EXISTS (
            SELECT 1 FROM ml_research_runs r
            WHERE r.id = ml_reports.run_id
              AND r.user_id = auth.uid()
        )
    );
```

The backend accesses the database using the Supabase **service role key** (bypasses RLS) for write operations inside the pipeline. The frontend uses the **anon key** (RLS enforced) for any direct Supabase SDK calls. All API requests through the FastAPI backend also enforce ownership in application code (the `user_id` filter is always applied), so there are two layers of isolation.

---

## Indexes

```sql
CREATE INDEX ON ml_research_runs (user_id);
CREATE INDEX ON ml_research_runs (status);
CREATE INDEX ON ml_source_urls   (run_id);
```

- `user_id` index on runs — the most common query pattern is "all runs for this user"
- `status` index on runs — used by the timeout watcher (scans for stuck active-status runs)
- `run_id` index on source_urls — used when loading a specific run's URLs

---

## Migrations

| File | Description |
|---|---|
| `001_initial.sql` | Creates all three tables, indexes, and RLS policies |
| `002_add_source_run_id.sql` | Adds `source_run_id` self-referential FK to `ml_research_runs` |

Migrations are applied manually via the Supabase SQL editor. There is no automatic migration runner in the current setup (see Future Scope for Alembic integration).
