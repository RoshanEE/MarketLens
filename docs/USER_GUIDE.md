# MarketLens — User Guide

## What Can You Do in MarketLens?

MarketLens lets you set up a research job by providing competitor names, topics, and source URLs. It crawls those pages, analyzes the content with AI, verifies each claim, and produces a structured intelligence report. You can re-run any report later to see what changed.

---

## Navigating the App

### 1. Login Page (`/login`)

The entry point if you are not authenticated.

- Enter your email and password and click **Sign In**
- If you don't have an account, click **Sign up** and provide your email and password (Supabase Auth handles confirmation)
- After sign-in you are redirected to the Dashboard

---

### 2. Dashboard (`/`)

The home screen. Shows all your previous research runs in a table, newest first.

**What you see in the table:**

| Column | Description |
|---|---|
| Title | Auto-generated from competitors/topics, or custom |
| Competitors / Topics | Labels showing what the run was researching |
| Status | Color-coded badge: Pending (grey), Running (blue), Complete (green), Failed (red) |
| Results | For completed runs: confidence score (color-coded) + verified/total claims |
| Created | When the run was started |
| Actions | View report, delete run |

**What you can do:**

- **Click a completed run** → opens the full report
- **Click a running/pending run** → opens the live pipeline progress view
- **Click the trash icon** → prompts to confirm deletion (deletes the run and all its data)
- **New Research** button (top right) → navigates to the research creation form

**Confidence score color coding:**
- Green (≥ 75%) — high confidence, most claims verified
- Amber (50–74%) — moderate confidence
- Red (< 50%) — low confidence, many claims unverified

---

### 3. New Research Page (`/new`)

Create a new research run.

**Form fields:**

| Field | Description | Required |
|---|---|---|
| Competitors | Company names to track (comma-separated or Enter-to-add) | At least one of competitors or topics |
| Topics | Research themes (e.g. "pricing", "product launch") | At least one of competitors or topics |
| Source URLs | Web pages to crawl and analyze | At least 1, max configurable (default 20) |
| Context | Optional free-text background for the AI (e.g. "We are a B2B SaaS company in the HR space") | No |

**Submitting:**
- Click **Start Research**
- The run is created immediately and you are taken to the **Pipeline Progress** view

---

### 4. Pipeline Progress View

Shows the live progress of a research run via a real-time event stream.

**Stages shown:**

| Stage | What's Happening |
|---|---|
| Crawling | Fetching content from each URL. Shows how many succeeded vs. failed. |
| Analyzing | AI reading the crawled content and extracting themes, competitor activities, and insights |
| Verifying | AI judge checking each claim against its source for accuracy |
| Complete | All done — report is ready |

- Failed URLs are listed under the Crawling step (the run continues with the successfully crawled URLs)
- If the entire run fails, an error message is shown explaining which stage failed
- When complete, a **View Report →** button appears

---

### 5. Report Page (`/report/:id`)

The full intelligence report for a completed run.

**Header bar:**
- Run title and date
- **Confidence score** — overall percentage of verified claims (color-coded)
- **Claims verified** — e.g. "10/12 claims verified"
- **Changes detected** badge — shown if this is a re-run and content changed (click to jump to the changes section)
- **Re-run** button — opens the Re-run modal
- **Back** button — returns to Dashboard

**Report sections:**

**Key Insights**
The most important cross-source findings. Each insight shows:
- The claim text
- Source URL and page title (clickable)
- Confidence score bar
- Verified / Unverified badge

**Themes**
Grouped patterns found across sources. Each theme has:
- A title and summary
- Expandable insights list (same structure as Key Insights)

**Competitor Activities**
Per-competitor findings. Each competitor section lists activities/announcements attributed to them with source links.

**Sources**
All URLs that were crawled, with their status:
- Green checkmark — successfully crawled
- Red warning icon — crawl failed (hover to see the error message)
- Page title and URL displayed

**Changes Detected** (re-runs only)
Shows what changed vs. the source run:
- **New URL** — a URL was added in this re-run that wasn't in the source run
- **Content Changed** — same URL, but the page content changed (different SHA-256 hash)
- **URL Removed** — a URL from the source run was not included in this re-run

---

### 6. Re-run Modal

Opened from the Report page via the **Re-run** button.

- Pre-populated with the current run's URLs, competitors, topics, and context
- You can add new URLs, remove existing ones, or change any field
- Submitting creates a new run with `source_run_id` pointing to the current run
- The new run's report will show change detection against this run's content

**Use cases:**
- Check if any source pages have been updated since the last run
- Add new competitor URLs to an existing research topic
- Expand the scope with more topics while keeping the same sources

---

## Tips

- **Adding URLs**: Paste one URL per line or comma-separated. The form validates that URLs start with `http://` or `https://`
- **Context field**: Providing context (e.g. your company's market position) helps the AI produce more targeted insights
- **Failed URLs**: If some URLs fail to crawl (paywalls, JavaScript-heavy sites, bot protection), the run continues with the rest. The report will note which sources were unavailable
- **Re-running**: After a few weeks, re-run a report to see what changed. The change detection shows exactly which URLs had content updates
- **Deleting a run**: Deleting a run removes all associated source URLs and reports. If a run is the source for other re-runs, those re-runs will lose their change detection reference (shown as no changes detected)
