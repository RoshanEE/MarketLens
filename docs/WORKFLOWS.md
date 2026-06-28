# MarketLens — Technical Workflows

## Frontend Workflows

### Authentication (Supabase Auth)

MarketLens uses Supabase's hosted auth service — no custom user table or password hashing is needed.

**Sign-in flow:**
1. User enters email + password on the Login page
2. `supabase.auth.signInWithPassword()` is called from the Supabase JS SDK
3. Supabase issues a JWT access token + refresh token, stored in `sessionStorage`
4. The Zustand `authStore` holds the session and `user` object in memory
5. `AuthGuard` wraps all protected routes — if no session exists, it redirects to `/login`
6. Every Axios API request includes the JWT in the `Authorization: Bearer` header (injected via an Axios request interceptor in `api.ts`)

**Sign-out:**
1. `supabase.auth.signOut()` clears the session from Supabase and localStorage
2. `authStore` is reset, user is redirected to `/login`

**Session persistence:**
- Supabase JS SDK automatically refreshes the access token using the refresh token before expiry
- On page reload, the SDK restores the session from storage without requiring re-login

---

### Creating a New Research Run

1. User navigates to **New Research** (`/new`)
2. Fills in the `ResearchForm`: competitors, topics, URLs (comma-separated), optional context
3. On submit: `POST /api/research/runs` — run is created with `status=pending` and SourceUrl rows inserted
4. Frontend receives the created run object (HTTP 201) and immediately opens an EventSource to `GET /api/research/runs/{id}/stream`
5. `PipelineProgress` component renders a step-by-step progress view driven by SSE events:
   - `crawling` → Step 1 active
   - `analyzing` → Step 2 active
   - `judging` → Step 3 active
   - `complete` → all steps done, "View Report →" button appears
   - `error` → error message displayed
6. On `complete` event, the frontend navigates to `/report/{id}`

---

### Viewing a Report

1. `ReportPage` fetches `GET /api/research/runs/{run_id}` for the full run + report
2. `ReportView` renders:
   - **Summary bar** — overall confidence score (color-coded: green ≥ 75%, amber ≥ 50%, red < 50%), claims verified count, change detection badge
   - **Key Insights** — top-level claims with source, confidence, verified badge
   - **Themes** — expandable theme cards, each with insights
   - **Competitor Activities** — grouped by competitor
   - **Sources** — list of all crawled URLs with crawl status; failed URLs show a hover tooltip with the error message
   - **Changes Detected** — if this is a re-run, lists new URLs, changed content, and removed URLs

---

### Re-running a Report

1. From `ReportPage`, user clicks **Re-run**
2. `RerunModal` opens, pre-populated with the current run's URLs, competitors, topics, and context
3. User can add/remove/change URLs or update other fields
4. On submit: `POST /api/research/runs` with `source_run_id: <current_run_id>` included
5. The new run tracks the source run for change detection — when the new report is generated, content hashes are compared against the source run
6. User is taken to the new run's pipeline progress view

---

### Dashboard

1. `DashboardPage` fetches `GET /api/research/runs` (paginated list)
2. `RunsTable` displays:
   - Run title, competitors/topics, status badge
   - Results column (confidence score + verified/total claims) for completed runs
   - Created date, actions (view report, delete)
3. Clicking a row for a `complete` run navigates to `/report/{id}`
4. Clicking a row for a `pending/running` run navigates to the pipeline progress stream view

---

## Backend Workflows

### Web Crawling — Why Trafilatura, not BeautifulSoup

BeautifulSoup is a general-purpose HTML parser — it gives you the entire DOM with all navigation menus, footers, ads, cookie banners, and sidebar widgets. Extracting "the article" from that requires writing custom CSS selectors for each site.

Trafilatura is purpose-built for article content extraction. It implements heuristics (similar to Mozilla Readability) to identify and return only the main content block — no nav, no boilerplate. This means:
- Less noise in the LLM prompt → higher quality analysis
- Lower token count → lower cost
- No per-site selector maintenance

BeautifulSoup is still used as a fallback when Trafilatura returns no content (e.g. heavily JavaScript-rendered pages, or unusual site structures).

When multiple URLs are crawled, requests are issued **concurrently** via `asyncio.gather` with individual `httpx` connections, so a single slow or failing URL doesn't block the rest.

---

### Content Chunking — Why Local Summarization Before Global Analysis

Long web pages (news articles, blog posts, press releases) can easily exceed the token budget for the global analysis prompt when multiple URLs are included. Naively truncating content loses information from the middle or end of pages where key facts often appear.

The chunking approach inspired by local summarization-ranking techniques (see [arxiv.org/html/2502.00448v1](https://arxiv.org/html/2502.00448v1)):

1. **Split** — the crawled text is split into paragraph-based chunks (~800 characters each). Short fragments (< 150 chars) are discarded as nav/caption noise.
2. **Summarize + Score** — a single LLM call (GPT-4.1-mini) receives all chunks for a URL and returns a one-sentence summary and a relevance score (0–10) for each chunk against the research query (competitors + topics). Doing scoring and summarization in one call is efficient and gives **semantic** relevance — synonyms and paraphrases are handled correctly, unlike keyword overlap.
3. **Select** — chunks scoring below a minimum relevance threshold (2.0/10) are discarded as off-topic. From the remaining, the top-8 highest-scoring chunks are kept, then **reordered to match their original document position** so the main analysis prompt reads naturally.
4. **Pass to global analysis** — only the selected, relevance-ranked content reaches GPT-4.1 for structured extraction.

If a page is already short (≤ 8 chunks), chunking is skipped entirely and the full content is passed through.

---

### AI Analysis — Global Summarizer (GPT-4.1)

The selected content from all URLs is concatenated into a single prompt with source metadata (URL, title). GPT-4.1 is instructed to extract a structured JSON object containing:

- **Themes** — cross-source patterns or trends, each with supporting claims
- **Competitor Activities** — per-competitor list of specific actions or announcements
- **Key Insights** — the most important single takeaways across all sources

Strict prompt rules prevent hallucination at the extraction stage:
- Every claim must be traceable to a sentence in the provided source text
- Competitors not explicitly named in the sources must not appear
- If sources contain nothing relevant, all arrays must be empty — no guessing

GPT-4.1 is used here (vs. the mini variant) because this step requires nuanced synthesis across multiple sources and produces the bulk of the report's value.

---

### LLM-as-a-Judge — Hallucination Verification (GPT-4.1-mini)

After extraction, every single claim in the report is independently verified:

1. Each claim is sent to GPT-4.1-mini alongside the source text it was attributed to
2. The judge answers: `supported (bool)`, `confidence (0.0–1.0)`, `reasoning (one sentence)`
3. Claims with `confidence ≥ 0.6` are marked `verified = true`
4. All verifications run **concurrently** via `asyncio.gather` to keep latency low
5. The overall confidence score is the mean of all individual confidences

GPT-4.1-mini is appropriate for the judge because:
- Each verification is an independent, focused binary question against a fixed context — no multi-source synthesis needed
- Running ~15 claims in parallel keeps total latency acceptable
- Cost is ~10× lower than GPT-4.1 for this high-volume step

---

### Change Detection

Change detection is only meaningful on a **re-run** (when a `source_run_id` is provided). On first run, no comparison is possible so `changes_detected = []`.

Algorithm:
1. After crawling, compute SHA-256 of each successfully crawled page's content
2. Fetch `content_hashes` from the source run (a JSONB column: `{ url → hash }`)
3. Compare:
   - URL in current but not in source run → `new_url`
   - URL in both but hashes differ → `content_changed`
   - URL in source run but not in current → `url_removed`
4. Store `changes_detected` in the Report row
5. Store the current run's `content_hashes` on the `ResearchRun` row for future re-runs

Using `source_run_id` as an explicit FK (rather than "compare against most recent run") means the user gets a diff against exactly the run they chose to re-run — predictable and unambiguous.

---

### Why No LangChain / LlamaIndex

The pipeline is a straightforward linear sequence: crawl → chunk → analyze → judge → persist. Using an orchestration framework like LangChain would add:
- A large dependency with frequent breaking changes
- Abstraction layers that obscure what the LLM is actually being sent
- Overhead for features (agent loops, memory, tool calling) that aren't needed here

A direct `llm.complete(system, user)` wrapper (`LLMClient`) over the OpenAI SDK keeps the codebase lightweight, debuggable, and easy to modify. Each stage is an ordinary async Python function.

---

### Why No Vector Database

Vector databases (Pinecone, Weaviate, pgvector) are valuable when you need semantic search over a large, persistent corpus — for example, "find all past reports mentioning pricing changes."

MarketLens processes a fresh, bounded set of URLs per run (typically 5–20 pages). The content fits in a single prompt after chunking. There's no retrieval problem to solve — the LLM receives all relevant content directly. Adding a vector DB would introduce operational overhead and cost with no accuracy benefit for this use case.

---

### Why Supabase Auth

Rolling custom JWT auth (issuing tokens, managing refresh, email verification, password reset flows) is significant undifferentiated work. Supabase Auth provides all of this out of the box:

- Email/password sign-in with email confirmation
- Automatic JWT issuance and refresh
- Works natively with Supabase PostgreSQL Row-Level Security (`auth.uid()` is available in SQL policies)
- No local JWT secret management needed — the backend delegates verification to `supabase.auth.get_user(token)` via the SDK
- Free tier is sufficient for this project

The tradeoff is a dependency on Supabase's auth infrastructure, but for a project of this scale that's a reasonable choice.
