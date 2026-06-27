"""
SQLAlchemy ORM models for research runs, source URLs, and generated reports.
All tables are prefixed with 'ml_' to avoid collision with Supabase auth tables.
"""

import uuid
from datetime import datetime
from sqlalchemy import String, Text, Float, ForeignKey, ARRAY, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


class ResearchRun(Base):
    __tablename__ = "ml_research_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(String(255))
    competitors: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    topics: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    context: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    error: Mapped[str | None] = mapped_column(Text)
    content_hashes: Mapped[dict] = mapped_column(JSONB, default=dict)  # url -> sha256 for change detection
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    source_urls: Mapped[list["SourceUrl"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    report: Mapped["Report | None"] = relationship(back_populates="run", cascade="all, delete-orphan", uselist=False)


class SourceUrl(Base):
    __tablename__ = "ml_source_urls"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ml_research_runs.id", ondelete="CASCADE"), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    page_title: Mapped[str | None] = mapped_column(Text)
    crawled_content: Mapped[str | None] = mapped_column(Text)
    content_hash: Mapped[str | None] = mapped_column(String(64))  # sha256 hex
    crawl_status: Mapped[str] = mapped_column(String(50), default="pending")
    error: Mapped[str | None] = mapped_column(Text)
    crawled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    run: Mapped["ResearchRun"] = relationship(back_populates="source_urls")


class Report(Base):
    __tablename__ = "ml_reports"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("ml_research_runs.id", ondelete="CASCADE"), unique=True, nullable=False
    )
    themes: Mapped[list] = mapped_column(JSONB, default=list)
    competitor_activities: Mapped[list] = mapped_column(JSONB, default=list)
    key_insights: Mapped[list] = mapped_column(JSONB, default=list)
    hallucination_results: Mapped[dict] = mapped_column(JSONB, default=dict)
    overall_confidence: Mapped[float | None] = mapped_column(Float)
    changes_detected: Mapped[list] = mapped_column(JSONB, default=list)  # for change detection stretch goal
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    run: Mapped["ResearchRun"] = relationship(back_populates="report")
