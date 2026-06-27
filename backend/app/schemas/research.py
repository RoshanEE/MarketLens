"""
Pydantic schemas for research run request/response serialization.
"""

from __future__ import annotations
from datetime import datetime
from uuid import UUID
from pydantic import BaseModel, field_validator, model_validator
from typing import Any


# ── Request schemas ────────────────────────────────────────────────────────────

class ResearchRunCreate(BaseModel):
    title: str | None = None
    competitors: list[str] = []
    topics: list[str] = []
    urls: list[str]
    context: str | None = None

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        from app.core.config import get_settings
        max_urls = get_settings().max_urls_per_run
        if not v:
            raise ValueError("At least one URL is required.")
        if len(v) > max_urls:
            raise ValueError(f"Maximum {max_urls} URLs per run.")
        return v

    @model_validator(mode="after")
    def must_have_competitors_or_topics(self) -> "ResearchRunCreate":
        if not self.competitors and not self.topics:
            raise ValueError("Provide at least one competitor name or topic.")
        return self


# ── Response schemas ───────────────────────────────────────────────────────────

class SourceUrlOut(BaseModel):
    id: UUID
    url: str
    page_title: str | None
    crawl_status: str
    error: str | None
    crawled_at: datetime | None

    model_config = {"from_attributes": True}


class InsightOut(BaseModel):
    claim: str
    source_url: str
    source_title: str | None
    confidence: float
    verified: bool
    judge_reasoning: str | None = None


class ThemeOut(BaseModel):
    title: str
    summary: str
    insights: list[InsightOut]


class CompetitorActivityOut(BaseModel):
    competitor: str
    activities: list[InsightOut]


class ReportOut(BaseModel):
    id: UUID
    run_id: UUID
    themes: list[ThemeOut]
    competitor_activities: list[CompetitorActivityOut]
    key_insights: list[InsightOut]
    overall_confidence: float | None
    changes_detected: list[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


class ResearchRunOut(BaseModel):
    id: UUID
    title: str | None
    competitors: list[str]
    topics: list[str]
    context: str | None
    status: str
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    source_urls: list[SourceUrlOut] = []
    report: ReportOut | None = None

    model_config = {"from_attributes": True}


class ResearchRunSummary(BaseModel):
    """Lightweight version for listing previous runs."""
    id: UUID
    title: str | None
    competitors: list[str]
    topics: list[str]
    status: str
    created_at: datetime
    completed_at: datetime | None
    url_count: int = 0

    model_config = {"from_attributes": True}


# ── SSE event schema ───────────────────────────────────────────────────────────

class ProgressEvent(BaseModel):
    event: str  # crawling | analyzing | judging | complete | error
    message: str
    detail: dict[str, Any] | None = None
