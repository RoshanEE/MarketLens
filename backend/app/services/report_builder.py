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

from app.models.research_run import ResearchRun, Report, SourceUrl
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
    changes = []
    for url, current_hash in current_hashes.items():
        prev_hash = previous_hashes.get(url)
        if prev_hash and prev_hash != current_hash:
            changes.append({"url": url, "type": "content_changed"})
        elif not prev_hash:
            changes.append({"url": url, "type": "new_url"})
    return changes


async def _get_previous_hashes(db: AsyncSession, user_id: UUID, urls: list[str]) -> dict[str, str]:
    """
    For each URL, find the most recent successful crawl hash across all previous
    completed runs by this user. This ensures change detection works correctly even
    when the user's last run used different URLs.
    """
    result = await db.execute(
        select(SourceUrl.url, SourceUrl.content_hash)
        .join(ResearchRun, SourceUrl.run_id == ResearchRun.id)
        .where(
            ResearchRun.user_id == user_id,
            ResearchRun.status == "complete",
            SourceUrl.url.in_(urls),
            SourceUrl.content_hash.isnot(None),
            SourceUrl.crawl_status == "success",
        )
        .order_by(SourceUrl.crawled_at.desc())
    )
    # Rows come back most-recent-first; take the first hash seen for each URL.
    url_hashes: dict[str, str] = {}
    for row in result.all():
        if row.url not in url_hashes:
            url_hashes[row.url] = row.content_hash
    return url_hashes


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

    try:
        # ── Stage 1: Crawling ─────────────────────────────────────────────────
        run.status = "crawling"
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

        successful = [r for r in crawl_results if r.status == "success"]
        failed = [r for r in crawl_results if r.status == "failed"]

        yield _make_event(
            "crawling",
            f"Crawled {len(successful)}/{len(urls)} URLs successfully.",
            detail={"failed": [r.url for r in failed]},
        )

        if not successful:
            run.status = "failed"
            run.error = "All URLs failed to crawl."
            await db.commit()
            yield _make_event("error", "All URLs failed to crawl.")
            return

        await db.commit()

        # ── Stage 2: AI Analysis ──────────────────────────────────────────────
        run.status = "analyzing"
        await db.commit()
        yield _make_event("analyzing", "Running AI analysis on extracted content…")

        crawl_dicts = [
            {"url": r.url, "title": r.title, "content": r.content}
            for r in successful
        ]

        analysis = await analyze_content(
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
        run.status = "judging"
        await db.commit()
        yield _make_event("judging", "Running hallucination verification on claims…")

        verified = await run_hallucination_check(analysis, crawl_dicts)

        yield _make_event(
            "judging",
            (
                f"Verified {verified['hallucination_results']['verified_claims']}/"
                f"{verified['hallucination_results']['total_claims']} claims. "
                f"Overall confidence: {verified['overall_confidence']:.0%}"
            ),
        )

        # ── Change Detection ──────────────────────────────────────────────────
        current_hashes = {r.url: r.content_hash for r in successful if r.content_hash}
        previous_hashes = await _get_previous_hashes(db, run.user_id, urls)
        changes = _detect_changes(current_hashes, previous_hashes)
        run.content_hashes = current_hashes

        # ── Stage 4: Persist Report ───────────────────────────────────────────
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

        run.status = "complete"
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(report)

        yield _make_event(
            "complete",
            "Research complete.",
            detail={"run_id": str(run.id), "report_id": str(report.id), "changes": changes},
        )

    except Exception as exc:
        log.error("pipeline.error", run_id=str(run_id), error=str(exc))
        run.status = "failed"
        run.error = str(exc)
        await db.commit()
        yield _make_event("error", f"Pipeline failed: {exc}")
