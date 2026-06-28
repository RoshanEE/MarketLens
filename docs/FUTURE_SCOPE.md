# MarketLens — Future Scope

## Pipeline & AI

**Scheduled re-runs**
Allow users to set a recurrence (weekly, monthly) on any research run. The system would automatically trigger a re-run and notify the user if changes are detected — turning MarketLens into a passive monitoring tool rather than a manual one.

**Email / Slack notifications**
On completion of a scheduled or manually triggered run, send a summary digest. If changes were detected, include a diff summary in the notification.

**Source discovery**
Instead of requiring users to supply URLs manually, add a discovery step: given a competitor name, automatically find recent relevant pages (press releases, blog posts, news articles) using a search API (e.g. Bing Web Search, SerpAPI). Users review the discovered URLs before the pipeline runs.

**Incremental crawling**
For re-runs, only re-crawl URLs where a change is likely (based on last-crawled date and site update frequency) rather than re-crawling everything. Reduces API cost and latency for large URL sets.

**Streaming analysis**
Stream the AI analysis response token-by-token so the pipeline progress view shows partial results appearing in real time rather than waiting for the full JSON response.

**Multi-model support**
Allow users to choose their preferred LLM provider per run (OpenAI, Anthropic, Google). The `LLMClient` abstraction already supports multiple providers — surfacing this choice in the UI is the main addition needed.

---

## Report Quality

**Claim deduplication**
The same claim can appear across themes, competitor activities, and key insights. A post-processing step to deduplicate identical or near-identical claims would improve report readability.

**Citation linking**
Deep-link each claim not just to the source URL but to the specific paragraph or sentence it came from (using fragment identifiers or a stored text offset). Makes fact-checking faster for the reader.

**Report comparison view**
Side-by-side diff between two runs of the same research topic — highlighting added, changed, and removed insights at the claim level (not just URL-level content hashes).

**Confidence calibration**
Track whether claims marked "verified" actually turn out to be accurate over time (e.g. via user feedback). Use this signal to recalibrate the confidence threshold or judge prompt.

---

## Data & Storage

**Alembic migrations**
Replace manual SQL migration files with Alembic for automatic schema versioning, rollback support, and migration history tracking.

**Report export**
Export reports as PDF or structured JSON for sharing outside the app or feeding into other tools (CRM, Notion, Google Docs).

**Full-text search**
Add a search bar on the Dashboard to search across all report content. Postgres `tsvector` full-text search on the JSONB report fields would be sufficient at this scale; no external search engine needed.

**Pagination and filtering on Dashboard**
Currently the dashboard loads the 20 most recent runs. Add pagination controls and filters by status, date range, or competitors.

---

## Infrastructure & DevOps

**Auto-deploy on merge to main**
Currently deployment is manual (workflow_dispatch). The workflows could be changed to trigger automatically on merge to `main` once a staging environment and smoke tests are in place.

**Staging environment**
A second Lightsail service + S3 bucket for a staging environment, automatically deployed on every push to `main`, with production deploy requiring manual promotion.

**Alembic + migration CI step**
Run `alembic upgrade head` as a step in the backend deploy workflow before rolling out the new container image.

**Backend autoscaling**
Lightsail Container Services support multiple nodes. Adding autoscaling based on CPU or request queue depth would handle concurrent research runs from multiple users without manual intervention.

**Observability**
Integrate structured logs (already using `structlog`) with a log aggregation service (Datadog, CloudWatch Logs Insights). Add distributed tracing (OpenTelemetry) across pipeline stages to diagnose slow runs.

---

## User Experience

**Team / organization support**
Allow multiple users to share a workspace, view each other's reports, and collaborate on research runs. Requires an `organization` table and updated RLS policies.

**Report templates**
Pre-defined research templates (e.g. "Competitor pricing analysis", "Feature launch monitoring") that pre-fill common topic and competitor combinations.

**Tagging and organization**
Allow users to tag runs and filter the dashboard by tag — useful once a user has dozens of research runs.

**Dark mode**
The UI is currently light-only. Tailwind's `dark:` variant classes make this straightforward to add.
