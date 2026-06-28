# MarketLens — Market Research Intelligence Assistant

A web application that helps product and GTM teams collect, analyze, and summarize competitive intelligence from public sources using AI.

---

## Problem Statement

Product and go-to-market teams struggle to stay current on competitor activity and market trends because relevant information is scattered across blogs, websites, announcements, and articles. Manually sifting through dozens of pages per week is slow, inconsistent, and hard to delegate.

MarketLens lets users provide a set of competitor names, research topics, and source URLs, then automatically crawls the content and generates a structured intelligence report — with every insight grounded in a verifiable source, and every claim independently verified by an LLM judge for accuracy.

---

## Solution Approach

1. **User input** — competitors, topics, source URLs, optional context
2. **Crawl** — Trafilatura (primary) + BeautifulSoup (fallback) extract clean article text from each URL concurrently
3. **Chunk & score** — long pages are split into paragraphs, scored for relevance to the research query by a fast LLM, and the top-K most relevant chunks are selected before analysis *(inspired by [arxiv.org/html/2502.00448v1](https://arxiv.org/html/2502.00448v1) — see [`docs/WORKFLOWS.md`](docs/WORKFLOWS.md) for details)*
4. **AI analysis** — GPT-4.1 generates structured themes, competitor activities, and key insights, each linked to a specific source URL
5. **Hallucination judge** — GPT-4.1-mini independently verifies each claim against its source text, attaching a confidence score and a verification flag
6. **Structured report** — rendered in the UI with source traceability, confidence indicators, and change detection vs. prior runs
7. **Re-run support** — users can re-run research with updated or expanded URLs; the report highlights what changed since the last run

---

## Getting Started

### Sign Up

Visit the app and click **Sign up**. Enter your email and password — Supabase Auth will send a verification email. Click the link in the email to confirm your account, then return to the app and sign in.

### After Signing In

You land on the **Dashboard**, which shows all your research runs. To create your first one, click **New Research** and fill in:

- **Competitors** — company names you want to track (e.g. "Notion", "Linear")
- **Topics** — themes to look for (e.g. "pricing", "product launch")
- **Source URLs** — the web pages to crawl and analyze
- **Context** *(optional)* — background about your company or angle, to help the AI produce more targeted insights

Once submitted, a live progress view shows the pipeline running in real time — crawling, analyzing, and verifying claims. When complete, the full report opens automatically.

### What You Can Do in a Report

- Read **Key Insights**, **Themes**, and **Competitor Activities** — each claim is linked to the exact source URL it came from
- Check the **confidence score** and **verified/total claims** count in the header to gauge report reliability
- Expand **"Generated against"** to see the full configuration the report was built from — competitors, topics, context, and all source URLs
- View **Sources** to see which URLs crawled successfully and hover over any failed URL to see the crawl error
- See **Changes Detected** (on re-runs) to understand what content changed since the last run
- Export the report as **PDF** using the download button in the report header
- Click **Re-run** to run the same research again — optionally adding or changing URLs — and get a fresh report with change detection

### Navigation

- **Dashboard** — overview of all runs with status, confidence score, and claims verified at a glance
- **New Research** — create a run
- **Report** — view any completed run's full report (accessible by clicking a row in the dashboard table)
- **Pipeline view** — opens automatically when a run is in progress; accessible by clicking an in-progress row in the dashboard

For a full walkthrough of every screen and action, see [`docs/USER_GUIDE.md`](docs/USER_GUIDE.md).

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, Tailwind CSS |
| Backend | FastAPI (Python 3.12), async SQLAlchemy |
| Auth | Supabase Auth (email/password, JWT) |
| Database | Supabase PostgreSQL (Row-Level Security) |
| Scraping | Trafilatura + BeautifulSoup4 |
| AI — Analysis | OpenAI GPT-4.1 (structured market intelligence extraction) |
| AI — Chunker & Judge | OpenAI GPT-4.1-mini (relevance scoring + claim verification) |
| Streaming | Server-Sent Events (SSE) for real-time pipeline progress |
| Containers | Docker (multi-stage builds) |
| CI/CD | GitHub Actions |
| Frontend Hosting | AWS S3 + CloudFront |
| Backend Hosting | AWS Lightsail Container Service |

---

## AI Tools Used

| Tool | Role |
|---|---|
| **Claude Code (Anthropic)** | AI coding assistant used during development of this project |
| **OpenAI GPT-4.1** | Global analysis — extracts structured themes, competitor activities, and key insights from crawled content |
| **OpenAI GPT-4.1-mini** | Local chunk summarization and LLM-as-a-judge hallucination verification |

---

## Local Development

### Prerequisites

- Python 3.12+
- Node 20+
- A [Supabase](https://supabase.com) project (free tier works)
- An [OpenAI](https://platform.openai.com) API key

### Without Docker

**1. Clone and configure**

```bash
git clone <repo-url>
cd MarketLens
```

Copy and fill in the environment files:

```bash
cp backend/.env.example backend/.env
# Fill in: SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY,
#          DATABASE_URL, OPENAI_API_KEY
```

```bash
cp frontend/.env.example frontend/.env
# Fill in: VITE_SUPABASE_URL, VITE_SUPABASE_ANON_KEY, VITE_API_BASE_URL
```

**2. Run database migrations**

Open your Supabase project SQL editor and run the migrations in order:

```
supabase/migrations/001_initial.sql   — tables, indexes, RLS policies
supabase/migrations/002_add_source_run_id.sql  — adds source_run_id FK for change detection
```

**3. Start the backend**

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

API docs available at `http://localhost:8000/docs` (debug mode only).

**4. Run the tests** (optional)

```bash
cd backend
pytest tests/ -v
```

Run a specific test file:

```bash
pytest tests/test_report_builder.py -v
```

Tests cover pure utility functions and do not require a live database or API keys.

**4. Start the frontend**

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

---

### With Docker Compose

```bash
# Copy and fill in env files first (see step 1 above), then:
docker compose up --build
```

- Frontend: `http://localhost:80`
- Backend: `http://localhost:8000`

Docker Compose starts both services, wires them together via the internal network, and runs a health check on the backend before marking the frontend as ready.

---

## Project Structure

```
MarketLens/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # FastAPI routers (auth, research, health)
│   │   ├── core/             # Config, DB session, security, deps
│   │   ├── models/           # SQLAlchemy ORM models + enums
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   └── services/         # crawler, chunker, ai_pipeline, judge, report_builder
│   ├── tests/                # pytest test suite
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/       # UI, layout, research, reports, auth
│   │   ├── hooks/            # useAuth, useSSE
│   │   ├── pages/            # Login, Dashboard, NewResearch, Report
│   │   ├── services/         # Supabase client, Axios API client
│   │   ├── store/            # Zustand auth store
│   │   └── types/            # Shared TypeScript types
│   └── Dockerfile
├── supabase/migrations/      # SQL schema, indexes, RLS policies
├── infrastructure/           # AWS CloudFormation template
├── .github/workflows/        # GitHub Actions CI/CD
├── docs/                     # Detailed architecture, workflows, DB design
└── docker-compose.yml
```

More detailed documentation on architecture, workflows, database design, deployment, and UI navigation is in the [`docs/`](docs/) folder.

---

## Stretch Goals Implemented

- **Change detection** — content hashes compared across re-runs; changed, new, and removed URLs are highlighted in the report
- **Source traceability** — every claim carries the exact source URL and page title
- **Confidence scoring** — each claim has a numeric confidence score and verified/unverified flag, with color-coded display in the UI
- **Re-run with diff** — re-run any report from the UI; the new report shows what changed vs. the run it was based on
- **Timeout watcher** — background task automatically marks stuck pipelines as failed after 30 minutes

---

## Accuracy & Limitations

MarketLens is designed to reduce manual research effort, not to replace human judgment. The current version applies several layers of accuracy control — relevance-based chunk selection, strict prompt rules that forbid inference across sources, and an independent LLM judge that flags unverified claims — but does not guarantee that every output is factually correct.

Factors that can affect accuracy:
- Source quality (paywalled, outdated, or JavaScript-rendered pages may not crawl cleanly)
- LLM hallucinations that pass the judge threshold
- Claims that are technically supported by the source text but lack wider context

Future versions can address this further through claim deduplication, confidence calibration against user feedback, and improved source discovery. See [`docs/FUTURE_SCOPE.md`](docs/FUTURE_SCOPE.md) for details on what can be implemented.
