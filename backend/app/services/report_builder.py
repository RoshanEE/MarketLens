"""
Orchestrates the full research pipeline:
1. Crawl URLs
2. AI analysis
3. Hallucination judge
4. Persist results to the database
5. Emit SSE progress events

This module is the single entry point called by the research route.
"""

import json
from datetime import datetime, timezone
from typing import AsyncGenerator
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.research_run import ResearchRun, Report
from app.models.enums import RunStatus, CrawlStatus
from app.services.crawler import crawl_urls, CrawlResult
from app.services.ai_pipeline import analyze_content
from app.services.judge import run_hallucination_check
from app.schemas.research import ProgressEvent

log = structlog.get_logger(__name__)


def _make_event(event: str, message: str, detail: dict | None = None) -> str:
    """Format a Server-Sent Event payload string."""
    payload = ProgressEvent(event=event, message=message, detail=detail).model_dump()
    return f"data: {json.dumps(payload)}\n\n"


def _detect_changes(current_hashes: dict[str, str], previous_hashes: dict[str, str]) -> list[dict]:
    """Compare content hashes between current and previous run for the same URLs."""
    if not previous_hashes:
        return []
    changes = []
    for url, current_hash in current_hashes.items():
        prev_hash = previous_hashes.get(url)
        if prev_hash is None:
            changes.append({"url": url, "type": "new_url"})
        elif prev_hash != current_hash:
            changes.append({"url": url, "type": "content_changed"})
    for url in previous_hashes:
        if url not in current_hashes:
            changes.append({"url": url, "type": "url_removed"})
    return changes


async def _get_previous_hashes(db: AsyncSession, source_run_id: UUID | None) -> dict[str, str]:
    """Fetch the content hashes stored on the source run for change detection."""
    if not source_run_id:
        return {}
    result = await db.execute(
        select(ResearchRun.content_hashes).where(ResearchRun.id == source_run_id)
    )
    return result.scalar_one_or_none() or {}


_USER_ERRORS: dict[str, str] = {
    "crawling":  "Step 1 of 3 (Crawling): Failed to fetch content from the source URLs. Check that all URLs are accessible and try again.",
    "analyzing": "Step 2 of 3 (Analysis): The AI model encountered an issue while analysing the content. Please try again.",
    "judging":   "Step 3 of 3 (Verification): The AI model encountered an issue while verifying claims. Please try again.",
    "saving":    "Failed to save the report to the database. Please try again.",
}


def _user_error(stage: str) -> str:
    return _USER_ERRORS.get(stage, "An unexpected error occurred. Please try again.")


async def _is_cancelled(db: AsyncSession, run_id: UUID) -> bool:
    """Re-query the run status to detect external cancellation (cancel endpoint or timeout watcher)."""
    result = await db.execute(
        select(ResearchRun.status).where(ResearchRun.id == run_id)
    )
    return result.scalar_one_or_none() == RunStatus.FAILED


async def run_research_pipeline(
    run_id: UUID,
    db: AsyncSession,
) -> AsyncGenerator[str, None]:
    """
    Full pipeline generator. Yields SSE-formatted strings that are streamed to the client.
    Updates the database at each stage.
    """
    # Load the run from DB
    result = await db.execute(
        select(ResearchRun)
        .where(ResearchRun.id == run_id)
        .options(selectinload(ResearchRun.source_urls))
    )
    run = result.scalar_one_or_none()
    if not run:
        yield _make_event("error", "Run not found.")
        return

    urls = [src.url for src in run.source_urls]

    _stage = "initializing"
    try:
        # ── Stage 1: Crawling ─────────────────────────────────────────────────
        _stage = "crawling"
        run.status = RunStatus.CRAWLING
        await db.commit()
        yield _make_event("crawling", f"Crawling {len(urls)} URL(s)…")

        crawl_results: list[CrawlResult] = await crawl_urls(urls)

        # Persist crawl results
        for src in run.source_urls:
            match = next((r for r in crawl_results if r.url == src.url), None)
            if match:
                src.page_title = match.title
                src.crawled_content = match.content
                src.content_hash = match.content_hash
                src.crawl_status = match.status
                src.error = match.error
                src.crawled_at = match.crawled_at

        successful = [r for r in crawl_results if r.status == CrawlStatus.SUCCESS]
        failed = [r for r in crawl_results if r.status == CrawlStatus.FAILED]

        for r in crawl_results:
            log.info("crawl.result", url=r.url, status=r.status.value, chars=len(r.content or ""))

        yield _make_event(
            "crawling",
            f"Crawled {len(successful)}/{len(urls)} URLs successfully.",
            detail={"failed": [r.url for r in failed]},
        )

        if not successful:
            run.status = RunStatus.FAILED
            run.error = "All URLs failed to crawl."
            await db.commit()
            yield _make_event("error", "All URLs failed to crawl.")
            return

        await db.commit()

        # ── Stage 2: AI Analysis ──────────────────────────────────────────────
        if await _is_cancelled(db, run_id):
            return

        _stage = "analyzing"
        run.status = RunStatus.ANALYZING
        await db.commit()
        yield _make_event("analyzing", "Running AI analysis on extracted content…")

        crawl_dicts = [
            {"url": r.url, "title": r.title, "content": r.content}
            for r in successful
        ]

        analysis, chunked_sources = await analyze_content(
            crawl_results=crawl_dicts,
            competitors=run.competitors or [],
            topics=run.topics or [],
            context=run.context,
        )

        yield _make_event(
            "analyzing",
            f"Analysis complete. Found {len(analysis.get('themes', []))} themes.",
        )

        # ── Stage 3: Hallucination Check ──────────────────────────────────────
        if await _is_cancelled(db, run_id):
            return

        _stage = "judging"
        run.status = RunStatus.JUDGING
        await db.commit()
        yield _make_event("judging", "Running hallucination verification on claims…")

        for s in chunked_sources:
            log.info("judge.source_input", url=s["url"], chars=len(s["content"] or ""))
        verified = await run_hallucination_check(analysis, chunked_sources)

        yield _make_event(
            "judging",
            (
                f"Verified {verified['hallucination_results']['verified_claims']}/"
                f"{verified['hallucination_results']['total_claims']} claims. "
                f"Overall confidence: {verified['overall_confidence']:.0%}" if verified['overall_confidence'] is not None else "Overall confidence: N/A"
            ),
        )

        # ── Change Detection ──────────────────────────────────────────────────
        if await _is_cancelled(db, run_id):
            return

        current_hashes = {r.url: r.content_hash for r in successful if r.content_hash}
        previous_hashes = await _get_previous_hashes(db, run.source_run_id)
        changes = _detect_changes(current_hashes, previous_hashes)
        run.content_hashes = current_hashes

        # ── Stage 4: Persist Report ───────────────────────────────────────────
        _stage = "saving"
        report = Report(
            run_id=run.id,
            themes=verified["themes"],
            competitor_activities=verified["competitor_activities"],
            key_insights=verified["key_insights"],
            hallucination_results=verified["hallucination_results"],
            overall_confidence=verified["overall_confidence"],
            changes_detected=changes,
        )
        db.add(report)

        run.status = RunStatus.COMPLETE
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(report)

        yield _make_event(
            "complete",
            "Research complete.",
            detail={"run_id": str(run.id), "report_id": str(report.id), "changes": changes},
        )

    except Exception as exc:
        log.error("pipeline.error", run_id=str(run_id), stage=_stage, error=str(exc))
        friendly = _user_error(_stage)
        run.status = RunStatus.FAILED
        run.error = friendly
        await db.commit()
        yield _make_event("error", friendly)
