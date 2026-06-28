"""
Background task that periodically finds runs stuck in an active status
for longer than STUCK_TIMEOUT_MINUTES and marks them as failed.

Covers two cases:
- Runs left in 'pending' because the SSE client never connected (e.g. server restart).
- Runs in 'crawling'/'analyzing'/'judging' where the pipeline hung mid-flight.
"""

import asyncio
from datetime import datetime, timezone, timedelta

import structlog
from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models.research_run import ResearchRun
from app.models.enums import RunStatus

log = structlog.get_logger(__name__)

STUCK_TIMEOUT_MINUTES = 30
_ACTIVE_STATUSES = (RunStatus.PENDING, RunStatus.CRAWLING, RunStatus.ANALYZING, RunStatus.JUDGING)
_CHECK_INTERVAL_SECONDS = 300


async def watch_for_stuck_runs() -> None:
    while True:
        await asyncio.sleep(_CHECK_INTERVAL_SECONDS)
        try:
            async with AsyncSessionLocal() as db:
                cutoff = datetime.now(timezone.utc) - timedelta(minutes=STUCK_TIMEOUT_MINUTES)
                result = await db.execute(
                    select(ResearchRun).where(
                        ResearchRun.status.in_(_ACTIVE_STATUSES),
                        ResearchRun.created_at < cutoff,
                    )
                )
                stuck = result.scalars().all()
                for run in stuck:
                    run.status = RunStatus.FAILED
                    run.error = (
                        f"Pipeline timed out after {STUCK_TIMEOUT_MINUTES} minutes "
                        "with no response. Please try again."
                    )
                    run.completed_at = datetime.now(timezone.utc)
                    log.warning("pipeline.timed_out", run_id=str(run.id), status=run.status)
                if stuck:
                    await db.commit()
                    log.info("timeout_watcher.cleaned_up", count=len(stuck))
        except Exception as exc:
            log.error("timeout_watcher.error", error=str(exc))
