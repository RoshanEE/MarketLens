"""
Research run routes.

POST /runs          — create a new run and its source URLs
GET  /runs          — list the authenticated user's previous runs
GET  /runs/{id}     — get a specific run with its report
GET  /runs/{id}/stream — SSE stream for live pipeline progress
DELETE /runs/{id}   — delete a run
"""

import asyncio
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import selectinload

from app.core.deps import get_current_user
from app.core.database import get_db
from app.models.research_run import ResearchRun, SourceUrl
from app.schemas.research import (
    ResearchRunCreate,
    ResearchRunOut,
    ResearchRunSummary,
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

    result = await db.execute(
        select(ResearchRun)
        .where(ResearchRun.user_id == user_id)
        .order_by(ResearchRun.created_at.desc())
        .offset(offset)
        .limit(limit)
        .options(selectinload(ResearchRun.source_urls))
    )
    runs = result.scalars().all()

    return [
        ResearchRunSummary(
            **{
                "id": r.id,
                "title": r.title,
                "competitors": r.competitors,
                "topics": r.topics,
                "status": r.status,
                "created_at": r.created_at,
                "completed_at": r.completed_at,
                "url_count": len(r.source_urls),
            }
        )
        for r in runs
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


@router.get("/{run_id}/stream")
async def stream_run(
    run_id: UUID,
    current_user: dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    SSE endpoint — starts the research pipeline and streams progress events.
    The client should connect immediately after creating a run.
    """
    user_id = UUID(current_user["sub"])
    await _get_run_or_404(db, run_id, user_id)  # ownership check

    async def event_stream():
        async for event in run_research_pipeline(run_id, db):
            yield event

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable nginx buffering
        },
    )


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
