# MarketLens — Architecture Reference

## System Overview

```
User Browser
     │
     │  (1) Supabase JS SDK — email/password auth
     ▼
Supabase Auth ──► issues JWT ──► stored in browser session
     │
     │  (2) JWT injected in every API request header
     ▼
Frontend (React/Vite — nginx)
     │
     │  HTTPS proxy (/api/*)
     ▼
Backend (FastAPI)
     │
     ├── /api/auth/me         — JWT validation, profile
     ├── /api/research/runs   — CRUD for research runs
     └── /api/research/runs/{id}/stream  — SSE pipeline
          │
          ├── 1. CrawlerService (Trafilatura + BS4)
          │        └── concurrent httpx requests per URL
          │
          ├── 2. AIPipelineService (Claude Sonnet)
          │        └── structured JSON extraction
          │
          ├── 3. JudgeService (Claude Haiku)
          │        └── parallel claim verification
          │
          └── 4. ReportBuilder
                   └── persist + stream events to frontend
     │
     ▼
Supabase PostgreSQL
  ├── ml_research_runs   (with RLS: user_id = auth.uid())
  ├── ml_source_urls     (with RLS: via run ownership)
  └── ml_reports         (with RLS: via run ownership)
```

## Request Flow: New Research Run

```
POST /api/research/runs
  └── Validate payload (Pydantic)
  └── Verify JWT (get_current_user dep)
  └── Create ResearchRun (status=pending) + SourceUrl rows
  └── Return run object (201)

GET /api/research/runs/{id}/stream  [EventSource]
  └── Verify JWT + ownership
  └── run_research_pipeline(run_id, db) → AsyncGenerator[str]
       ├── Stage 1: crawl_urls() — concurrent
       │     ├── trafilatura.extract()
       │     └── BeautifulSoup fallback
       │     └── Update SourceUrl rows in DB
       │     └── yield SSE "crawling" events
       ├── Stage 2: analyze_content() — Claude Sonnet
       │     └── Format sources → single prompt
       │     └── Parse JSON response
       │     └── yield SSE "analyzing" event
       ├── Stage 3: run_hallucination_check() — Claude Haiku
       │     └── asyncio.gather over all claims
       │     └── Each claim: judge prompt → confidence + reasoning
       │     └── yield SSE "judging" event
       └── Stage 4: Persist Report
             └── content hash comparison for change detection
             └── DB insert Report row
             └── Update run.status = "complete"
             └── yield SSE "complete" event
```

## Data Model

```
auth.users (Supabase managed)
    │
    └──< ml_research_runs
              id, user_id, title, competitors[], topics[],
              context, status, error, content_hashes (JSONB),
              created_at, completed_at
              │
              └──< ml_source_urls
              │         id, run_id, url, page_title,
              │         crawled_content, content_hash,
              │         crawl_status, error, crawled_at
              │
              └──1 ml_reports
                        id, run_id,
                        themes (JSONB),
                        competitor_activities (JSONB),
                        key_insights (JSONB),
                        hallucination_results (JSONB),
                        overall_confidence, changes_detected,
                        created_at
```

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
          "source_title": "string|null",
          "confidence": 0.0-1.0,
          "verified": true/false,
          "judge_reasoning": "string|null"
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
  }
}
```

## Security

- **Auth**: Supabase JWT (HS256). Backend verifies signature using `SUPABASE_JWT_SECRET`.
- **RLS**: All DB tables have Row-Level Security enforced at the Postgres layer (`auth.uid() = user_id`).
- **Secrets**: Never committed. Loaded from environment variables (`.env` files, ECS task definition secrets).
- **CORS**: Explicit allowlist via `CORS_ORIGINS` env var.
- **Non-root container**: Backend Docker image runs as `appuser`, not root.

## Cost Considerations

| Operation | Model | Est. tokens per run (5 URLs) |
|---|---|---|
| Analysis | Claude Sonnet | ~8k input, ~2k output |
| Judge (per claim, ~15 claims) | Claude Haiku | ~4k input, ~0.5k output total |

Haiku for the judge vs. Sonnet cuts per-run AI cost by ~10× for that step.
