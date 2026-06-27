# MarketLens — Market Research Intelligence Assistant

A web application that helps product and GTM teams collect, analyze, and summarize competitive intelligence from public sources using AI.

---

## Problem Statement

Product and go-to-market teams struggle to stay current on competitor activity and market trends because relevant information is scattered across blogs, websites, announcements, and articles. MarketLens lets users provide a set of competitor names, research topics, and source URLs, then automatically crawls the content and generates a structured intelligence report — with every insight grounded in a verifiable source, and claims verified by an independent LLM judge.

---

## Solution Approach

1. **User input** — competitors, topics, source URLs, optional context
2. **Crawl** — Trafilatura (primary) + BeautifulSoup (fallback) extract clean article text
3. **AI analysis** — Claude Sonnet generates structured themes, competitor activities, and key insights, each linked to a source URL
4. **Hallucination judge** — Claude Haiku independently verifies each claim against its source, attaching a confidence score and verification flag
5. **Structured report** — rendered in the UI with source traceability, confidence indicators, and change detection vs. prior runs

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | React 18, Vite, TypeScript, Tailwind CSS |
| Backend | FastAPI (Python 3.12), async SQLAlchemy |
| Auth | Supabase Auth (JWT / email+password) |
| Database | Supabase PostgreSQL (with Row-Level Security) |
| Scraping | Trafilatura + BeautifulSoup4 |
| AI | Anthropic Claude (Sonnet for analysis, Haiku for judge) |
| Streaming | Server-Sent Events (SSE) for real-time pipeline progress |
| Containers | Docker (multi-stage builds) |
| CI/CD | GitHub Actions → ECR → AWS ECS |

---

## Local Development

### Prerequisites

- Python 3.12+
- Node 20+
- A [Supabase](https://supabase.com) project (free tier is fine)
- An [Anthropic](https://console.anthropic.com) API key

### 1. Clone and configure

```bash
git clone <repo-url>
cd MarketLens
```

**Backend environment:**

```bash
cp backend/.env.example backend/.env
# Edit backend/.env with your Supabase credentials, DB URL, and API keys
```

**Frontend environment:**

```bash
cp frontend/.env.example frontend/.env
# Edit frontend/.env with your Supabase URL and anon key
```

### 2. Run the database migration

Open your Supabase project SQL editor and paste the contents of `supabase/migrations/001_initial.sql`, then run it. This creates the tables and Row-Level Security policies.

### 3. Start the backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

The API docs are available at `http://localhost:8000/docs` (debug mode only).

### 4. Start the frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

### 5. Or use Docker Compose

```bash
docker compose up --build
```

Frontend: `http://localhost:80` · Backend: `http://localhost:8000`

---

## Project Structure

```
MarketLens/
├── backend/
│   ├── app/
│   │   ├── api/routes/       # FastAPI routers (auth, research, health)
│   │   ├── core/             # Config, DB, security, deps
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/         # crawler, ai_pipeline, judge, report_builder
│   │   └── main.py
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── components/       # UI, layout, research, reports
│   │   ├── hooks/            # useAuth, useSSE
│   │   ├── pages/            # Login, Dashboard, NewResearch, Report
│   │   ├── services/         # Supabase client, Axios API client
│   │   ├── store/            # Zustand auth store
│   │   └── types/            # Shared TypeScript types
│   └── Dockerfile
├── supabase/migrations/      # SQL schema and RLS policies
├── .github/workflows/        # GitHub Actions CI/CD
└── docker-compose.yml
```

---

## AI Tools, Models, and Libraries Used

| Tool / Model | Usage | Reference |
|---|---|---|
| Claude Sonnet (`claude-sonnet-4-6`) | Primary market intelligence analysis | [Anthropic Docs](https://docs.anthropic.com) |
| Claude Haiku (`claude-haiku-4-5-20251001`) | Hallucination judge — cheaper, focused fact-check task | [Anthropic Docs](https://docs.anthropic.com) |
| Trafilatura | Main content extraction from web articles | [trafilatura.readthedocs.io](https://trafilatura.readthedocs.io) |
| BeautifulSoup4 | Fallback HTML parsing | [beautiful-soup-4.readthedocs.io](https://beautiful-soup-4.readthedocs.io) |
| Claude Code (Anthropic) | AI-assisted development of this codebase | claude.ai/code |

---

## Design Decisions and Trade-offs

### Supabase Auth over rolling custom JWT
Supabase handles token issuance, refresh, email verification, and RLS policy enforcement out of the box. The backend simply verifies the HS256 JWT using the project's JWT secret — no auth service to maintain.

### SSE over WebSockets
Server-Sent Events are simpler to implement and debug for a unidirectional push stream (server → client). WebSockets would add complexity without benefit here since the client only reads progress, never writes back during a run.

### Trafilatura as primary scraper
Trafilatura is purpose-built for extracting main article content (removes nav, ads, boilerplate). BeautifulSoup without custom rules would include page noise that degrades AI analysis quality and increases token consumption.

### Two-model approach for hallucination checking
Using a cheaper, faster model (Haiku) for the judge keeps per-run costs low while still providing independent verification. Sending all claims in parallel via `asyncio.gather` keeps latency acceptable.

### JSONB for report storage
Report structure (themes, insights, competitor activities) may evolve. JSONB gives flexibility to add fields without schema migrations, while still being queryable in Postgres.

### Change detection via content hashing
SHA-256 hashing of extracted content on each run lets us cheaply detect "what's new" by comparing against the previous run's hashes — no diff service needed.

### Row-Level Security
All tables enforce RLS so users can only access their own data — even if the API layer has a bug, the database enforces isolation.

---

## Deployment (AWS)

The GitHub Actions workflow in `.github/workflows/deploy.yml` handles the full pipeline:

1. Lint backend (ruff) and frontend (eslint)
2. Build multi-stage Docker images for both services
3. Push to Amazon ECR
4. Deploy to ECS (force new deployment) and wait for stability

**Required GitHub Secrets:** `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_REGION`, `ECR_REGISTRY`, `ECS_CLUSTER`, `ECS_SERVICE_BACKEND`, `ECS_SERVICE_FRONTEND`

---

## Stretch Goals Implemented

- **Change detection** — content hashes compared across runs; changed URLs highlighted in the report
- **Source traceability** — every insight carries the exact source URL and page title
- **Confidence scoring** — each claim has a numeric confidence and verified/unverified flag
