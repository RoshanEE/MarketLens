# MarketLens — Architecture Reference

## System Overview

```
User Browser
     │
     │  (1) Supabase JS SDK — email/password sign-in
     ▼
Supabase Auth ──► issues JWT ──► stored in browser session storage
     │
     │  (2) JWT sent as Authorization: Bearer <token> on every API call
     ▼
Frontend (React + Vite — served via Nginx / CloudFront)
     │
     │  HTTP/HTTPS  (/api/*)
     ▼
Backend (FastAPI — AWS Lightsail Container Service)
     │
     │  Every request: get_current_user dep → Supabase SDK verifies JWT
     │
     ├── POST /api/research/runs         — create run, return immediately
     ├── GET  /api/research/runs         — list runs (single optimized query)
     ├── GET  /api/research/runs/{id}    — fetch run + full report
     ├── GET  /api/research/runs/{id}/stream  — SSE pipeline execution
     ├── PATCH /api/research/runs/{id}   — update title
     ├── POST  /api/research/runs/{id}/cancel
     ├── DELETE /api/research/runs/{id}
     └── GET /api/auth/me                — validate token, return profile
          │
          └── Pipeline (stream endpoint only)
               ├── 1. CrawlerService
               │        concurrent httpx fetches per URL
               │        Trafilatura (primary) → BeautifulSoup (fallback)
               │
               ├── 2. ContentChunker (per URL, concurrent)
               │        split → LLM summarize+score → select top-K chunks
               │        model: GPT-4.1-mini
               │
               ├── 3. AIPipelineService
               │        format selected chunks into single prompt
               │        extract themes, competitor activities, key insights
               │        model: GPT-4.1
               │
               ├── 4. JudgeService
               │        verify each claim against source text (concurrent)
               │        attach confidence score + verified flag
               │        model: GPT-4.1-mini
               │
               └── 5. ReportBuilder
                        SHA-256 change detection vs. source run
                        persist Report row to DB
                        stream SSE events throughout
     │
     ▼
Supabase PostgreSQL
  ├── ml_research_runs   (RLS: auth.uid() = user_id)
  ├── ml_source_urls     (RLS: via run ownership join)
  └── ml_reports         (RLS: via run ownership join)
```

---

## Request Flow: New Research Run

```
POST /api/research/runs
  └── Pydantic validates payload (URLs, competitors/topics required)
  └── get_current_user dep → Supabase SDK verifies JWT
  └── Create ResearchRun (status=pending) + SourceUrl rows in DB
  └── Return run object (HTTP 201)

GET /api/research/runs/{id}/stream  [EventSource opened by frontend]
  └── Verify JWT + ownership
  └── If status == complete → emit single "complete" SSE and close
  └── If status == failed  → emit single "error"  SSE and close
  └── If status == pending → start pipeline in asyncio background task
       │
       ├── Stage 1: Crawling
       │     run.status = "crawling"
       │     concurrent httpx requests (one per URL)
       │     trafilatura.extract() → content + title
       │     fallback: BeautifulSoup text extraction
       │     persist crawl_status, page_title, content_hash per SourceUrl
       │     yield SSE "crawling" events (start, summary)
       │     abort if 0 URLs succeeded
       │
       ├── Stage 2: AI Analysis
       │     run.status = "analyzing"
       │     yield SSE "analyzing" event
       │     ContentChunker per URL (concurrent):
       │       split into ~800-char paragraph chunks
       │       LLM: summarize + score each chunk (GPT-4.1-mini)
       │       keep top-8 chunks above relevance threshold
       │     Format selected chunks → single prompt
       │     GPT-4.1 → JSON: themes, competitor_activities, key_insights
       │
       ├── Stage 3: Hallucination Judge
       │     run.status = "judging"
       │     yield SSE "judging" event
       │     All claims (theme + competitor + key_insights) judged concurrently
       │     GPT-4.1-mini: supported (bool) + confidence (0-1) + reasoning
       │     Claims with confidence ≥ 0.6 marked verified=true
       │     Compute overall_confidence, verified_claims, total_claims
       │
       ├── Change Detection
       │     Only runs when source_run_id is set (i.e. this is a re-run)
       │     SHA-256 hash of crawled content per URL (stored on source run)
       │     Compare current_hashes vs previous_hashes:
       │       new_url      — URL present now, absent from source run
       │       content_changed — same URL, different hash
       │       url_removed  — URL present in source run, absent now
       │
       └── Stage 4: Persist Report
             run.status = "complete"
             Insert Report row with themes, competitor_activities,
               key_insights, hallucination_results, overall_confidence,
               changes_detected, created_at
             Update run.content_hashes (for future change detection)
             yield SSE "complete" event with report_id + changes
```

---

## Authentication Flow

```
Frontend                    Supabase Auth               Backend (FastAPI)
    │                            │                            │
    │── email + password ───────►│                            │
    │◄── JWT (access_token) ─────│                            │
    │    stored in sessionStorage │                            │
    │                            │                            │
    │── API request ─────────────────────────────────────────►│
    │   Authorization: Bearer <JWT>                           │
    │                            │                            │
    │                            │◄── get_user(JWT) ──────────│
    │                            │                            │
    │                            │─── user object ───────────►│
    │                            │    (id, email, role)       │
    │                            │                            │
    │◄──────────────────────────────────── response ──────────│
```

JWT verification is handled entirely by the Supabase SDK (`client.auth.get_user(token)`). The backend does not need to hold the JWT secret or implement JWT parsing — Supabase validates the signature and expiry server-side.

---

## Data Model

```
auth.users  (Supabase managed — UUID primary key)
    │
    └──< ml_research_runs
    │         id             UUID PK
    │         user_id        UUID FK → auth.users
    │         title          TEXT
    │         competitors    TEXT[]
    │         topics         TEXT[]
    │         context        TEXT (optional)
    │         status         TEXT  (pending | crawling | analyzing | judging | complete | failed)
    │         error          TEXT (friendly user-facing message on failure)
    │         source_run_id  UUID FK → ml_research_runs (self-ref, SET NULL on delete)
    │         content_hashes JSONB  { url → sha256_hash }
    │         created_at     TIMESTAMPTZ
    │         completed_at   TIMESTAMPTZ
    │
    ├──< ml_source_urls
    │         id             UUID PK
    │         run_id         UUID FK → ml_research_runs
    │         url            TEXT
    │         page_title     TEXT
    │         crawled_content TEXT
    │         content_hash   TEXT  (SHA-256 of crawled_content)
    │         crawl_status   TEXT  (pending | success | failed)
    │         error          TEXT
    │         crawled_at     TIMESTAMPTZ
    │
    └──1 ml_reports
              id                    UUID PK
              run_id                UUID FK → ml_research_runs (unique)
              themes                JSONB
              competitor_activities JSONB
              key_insights          JSONB
              hallucination_results JSONB
              overall_confidence    FLOAT
              changes_detected      JSONB[]
              created_at            TIMESTAMPTZ
```

---

## JSONB Report Schema

```json
{
  "themes": [
    {
      "title": "string",
      "summary": "string",
      "insights": [
        {
          "claim": "string",
          "source_url": "string",
          "source_title": "string | null",
          "confidence": 0.0,
          "verified": true,
          "judge_reasoning": "string | null"
        }
      ]
    }
  ],
  "competitor_activities": [
    {
      "competitor": "string",
      "activities": [ /* same Insight shape */ ]
    }
  ],
  "key_insights": [ /* same Insight shape */ ],
  "hallucination_results": {
    "total_claims": 12,
    "verified_claims": 10,
    "unverified_claims": 2,
    "overall_confidence": 0.87,
    "confidence_threshold": 0.6
  },
  "changes_detected": [
    { "url": "https://example.com", "type": "content_changed" },
    { "url": "https://new.com",     "type": "new_url" },
    { "url": "https://gone.com",    "type": "url_removed" }
  ]
}
```

---

## Security

| Concern | Mechanism |
|---|---|
| Auth | Supabase JWT verified via Supabase SDK on every request |
| Data isolation | Row-Level Security on all DB tables (`auth.uid() = user_id`) |
| Secrets | Never committed; passed via env vars and GitHub Secrets |
| CORS | Explicit allowlist via `CORS_ORIGINS` env var |
| Container | Backend runs as non-root `appuser` |
| RLS bypass prevention | Even if API layer has a bug, Postgres enforces isolation |

---

## Cost Profile (per run, ~5 URLs)

| Step | Model | Approx. tokens |
|---|---|---|
| Chunk summarization (per URL) | GPT-4.1-mini | ~2k in, ~0.5k out |
| Global analysis | GPT-4.1 | ~8k in, ~2k out |
| Judge (per claim, ~15 claims) | GPT-4.1-mini | ~4k in total, ~0.5k out |

Using GPT-4.1-mini for chunking and judging vs. GPT-4.1 cuts per-run AI cost by ~10× for those steps while maintaining quality for the focused verification task.
