"""
Research run routes.

POST /runs          — create a new run and its source URLs
GET  /runs          — list the authenticated user's previous runs
GET  /runs/{id}     — get a specific run with its report
GET  /runs/{id}/stream — SSE stream for live pipeline progress
DELETE /runs/{id}   — delete a run
"""

import asyncio
import json
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.database import get_db, AsyncSessionLocal
from app.models.research_run import ResearchRun, SourceUrl, Report
from app.models.enums import RunStatus
from app.schemas.research import (
    ResearchRunCreate,
    ResearchRunOut,
    ResearchRunSummary,
    ResearchRunUpdate,
)
from app.services.report_builder import run_research_pipeline

router = APIRouter(prefix="/runs", tags=["research"])


@router.post("", response_model=ResearchRunOut, status_code=status.HTTP_201_CREATED)
async def create_run(
    payload: ResearchRunCreate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new research run. Returns the run record immediately (status=pending)."""
    user_id = UUID(current_user["sub"])

    run = ResearchRun(
        user_id=user_id,
        title=payload.title or _auto_title(payload),
        competitors=payload.competitors,
        topics=payload.topics,
        context=payload.context,
        source_run_id=payload.source_run_id,
        status="pending",
    )
    db.add(run)
    await db.flush()  # get run.id before adding children

    for url in payload.urls:
        db.add(SourceUrl(run_id=run.id, url=url))

    await db.commit()
    await db.refresh(run)

    # Eagerly reload relationships for the response
    result = await db.execute(
        select(ResearchRun)
        .where(ResearchRun.id == run.id)
        .options(selectinload(ResearchRun.source_urls), selectinload(ResearchRun.report))
    )
    run = result.scalar_one()
    return run


@router.get("", response_model=list[ResearchRunSummary])
async def list_runs(
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = 20,
    offset: int = 0,
):
    """List all research runs for the authenticated user, newest first."""
    user_id = UUID(current_user["sub"])

    url_count_sq = (
        select(func.count(SourceUrl.id))
        .where(SourceUrl.run_id == ResearchRun.id)
        .correlate(ResearchRun)
        .scalar_subquery()
    )

    result = await db.execute(
        select(
            ResearchRun.id,
            ResearchRun.title,
            ResearchRun.competitors,
            ResearchRun.topics,
            ResearchRun.status,
            ResearchRun.created_at,
            ResearchRun.completed_at,
            url_count_sq.label("url_count"),
            Report.overall_confidence,
            Report.hallucination_results,
        )
        .outerjoin(Report, Report.run_id == ResearchRun.id)
        .where(ResearchRun.user_id == user_id)
        .order_by(ResearchRun.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()

    return [
        ResearchRunSummary(
            id=row.id,
            title=row.title,
            competitors=row.competitors,
            topics=row.topics,
            status=row.status,
            created_at=row.created_at,
            completed_at=row.completed_at,
            url_count=row.url_count,
            overall_confidence=row.overall_confidence,
            verified_claims=(row.hallucination_results or {}).get("verified_claims") if row.hallucination_results else None,
            total_claims=(row.hallucination_results or {}).get("total_claims") if row.hallucination_results else None,
        )
        for row in rows
    ]


@router.get("/{run_id}", response_model=ResearchRunOut)
async def get_run(
    run_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Fetch a specific run with its full report."""
    user_id = UUID(current_user["sub"])
    run = await _get_run_or_404(db, run_id, user_id)
    return run


_SSE_HEADERS = {"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}


def _sse(event: str, message: str, detail: dict | None = None) -> str:
    return f"data: {json.dumps({'event': event, 'message': message, 'detail': detail})}\n\n"


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE endpoint — starts the research pipeline and streams progress events.
    Only starts the pipeline when the run is in 'pending' status.
    For complete/failed runs, emits a single terminal event and closes.
    For already-running pipelines (crawling/analyzing/judging), returns 409
    so the client can poll instead of accidentally restarting the pipeline.
    """
    user_id = UUID(current_user["sub"])
    run = await _get_run_or_404(db, run_id, user_id)

    if run.status == RunStatus.COMPLETE:
        report_id = str(run.report.id) if run.report else None
        async def _done():
            yield _sse("complete", "Research complete.", {"run_id": str(run_id), "report_id": report_id, "changes": []})
        return StreamingResponse(_done(), media_type="text/event-stream", headers=_SSE_HEADERS)

    if run.status == RunStatus.FAILED:
        async def _failed():
            yield _sse("error", run.error or "Pipeline failed.")
        return StreamingResponse(_failed(), media_type="text/event-stream", headers=_SSE_HEADERS)

    if run.status != RunStatus.PENDING:
        # Pipeline is already running — refuse to restart it.
        # The frontend should poll GET /runs/{id} until complete/failed.
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Pipeline is already in progress. Poll GET /runs/{id} for status updates.",
        )

    # Run the pipeline in a background task with its own DB session so it
    # survives if the SSE client disconnects before the pipeline finishes.
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    async def _background_pipeline() -> None:
        async with AsyncSessionLocal() as task_db:
            try:
                async for event in run_research_pipeline(run_id, task_db):
                    await queue.put(event)
            except Exception:
                pass
            finally:
                await queue.put(None)  # sentinel: pipeline done

    asyncio.create_task(_background_pipeline())

    async def event_stream():
        while True:
            event = await queue.get()
            if event is None:
                break
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers=_SSE_HEADERS,
    )


@router.patch("/{run_id}", response_model=ResearchRunOut)
async def update_run(
    run_id: UUID,
    payload: ResearchRunUpdate,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update mutable fields of a run (currently: title)."""
    user_id = UUID(current_user["sub"])
    run = await _get_run_or_404(db, run_id, user_id)
    run.title = payload.title.strip() or run.title
    await db.commit()
    await db.refresh(run)
    return run


@router.post("/{run_id}/cancel", response_model=ResearchRunOut)
async def cancel_run(
    run_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Cancel an in-progress run. No-op if the run is already complete or failed."""
    user_id = UUID(current_user["sub"])
    run = await _get_run_or_404(db, run_id, user_id)

    if run.status not in (RunStatus.COMPLETE, RunStatus.FAILED):
        run.status = RunStatus.FAILED
        run.error = "Cancelled by user."
        run.completed_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(run)

    return run


@router.delete("/{run_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_run(
    run_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a run and all associated data (cascades to source_urls and report)."""
    user_id = UUID(current_user["sub"])
    run = await _get_run_or_404(db, run_id, user_id)
    await db.delete(run)
    await db.commit()


# ── Helpers ────────────────────────────────────────────────────────────────────

async def _get_run_or_404(db: AsyncSession, run_id: UUID, user_id: UUID) -> ResearchRun:
    result = await db.execute(
        select(ResearchRun)
        .where(ResearchRun.id == run_id, ResearchRun.user_id == user_id)
        .options(selectinload(ResearchRun.source_urls), selectinload(ResearchRun.report))
    )
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found.")
    return run


def _auto_title(payload: ResearchRunCreate) -> str:
    parts = payload.competitors[:2] + payload.topics[:2]
    return "Research: " + ", ".join(parts)[:80] if parts else "Untitled Research"
