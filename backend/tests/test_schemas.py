"""
Tests for the Pydantic request/response schemas.

Focuses on ResearchRunCreate validators since they contain custom business logic.
Other schemas are straightforward Pydantic models with no custom validators.
"""

import pytest
from pydantic import ValidationError

from app.schemas.research import ResearchRunCreate, ProgressEvent


# ---------------------------------------------------------------------------
# ResearchRunCreate validators
# ---------------------------------------------------------------------------

class TestResearchRunCreate:
    def _valid(self, **overrides) -> dict:
        base = {"urls": ["https://example.com"], "competitors": ["Apple"]}
        return {**base, **overrides}

    # ── URL validation ──────────────────────────────────────────────────────

    def test_valid_with_single_url_and_competitor(self):
        schema = ResearchRunCreate(**self._valid())
        assert schema.urls == ["https://example.com"]
        assert schema.competitors == ["Apple"]

    def test_empty_urls_list_raises_validation_error(self):
        with pytest.raises(ValidationError, match="At least one URL"):
            ResearchRunCreate(**self._valid(urls=[]))

    def test_exceeding_max_urls_raises_validation_error(self):
        # Default max_urls_per_run is 10; 11 should fail
        too_many = [f"https://example{i}.com" for i in range(11)]
        with pytest.raises(ValidationError, match="Maximum"):
            ResearchRunCreate(**self._valid(urls=too_many))

    def test_exactly_max_urls_is_accepted(self):
        max_urls = [f"https://example{i}.com" for i in range(10)]
        schema = ResearchRunCreate(**self._valid(urls=max_urls))
        assert len(schema.urls) == 10

    # ── Competitors / topics validation ─────────────────────────────────────

    def test_no_competitors_and_no_topics_raises_validation_error(self):
        with pytest.raises(ValidationError, match="at least one competitor"):
            ResearchRunCreate(urls=["https://example.com"], competitors=[], topics=[])

    def test_competitors_only_is_valid(self):
        schema = ResearchRunCreate(urls=["https://example.com"], competitors=["Apple"], topics=[])
        assert schema.competitors == ["Apple"]
        assert schema.topics == []

    def test_topics_only_is_valid(self):
        schema = ResearchRunCreate(urls=["https://example.com"], competitors=[], topics=["pricing"])
        assert schema.topics == ["pricing"]
        assert schema.competitors == []

    def test_both_competitors_and_topics_is_valid(self):
        schema = ResearchRunCreate(
            urls=["https://example.com"],
            competitors=["Apple"],
            topics=["pricing"],
        )
        assert schema.competitors == ["Apple"]
        assert schema.topics == ["pricing"]

    # ── Optional fields ──────────────────────────────────────────────────────

    def test_title_defaults_to_none(self):
        schema = ResearchRunCreate(**self._valid())
        assert schema.title is None

    def test_title_accepted_when_provided(self):
        schema = ResearchRunCreate(**self._valid(title="Q4 Research"))
        assert schema.title == "Q4 Research"

    def test_context_defaults_to_none(self):
        schema = ResearchRunCreate(**self._valid())
        assert schema.context is None

    def test_context_accepted_when_provided(self):
        schema = ResearchRunCreate(**self._valid(context="Focus on EMEA."))
        assert schema.context == "Focus on EMEA."

    def test_multiple_urls_and_competitors_accepted(self):
        schema = ResearchRunCreate(
            urls=["https://a.com", "https://b.com"],
            competitors=["Apple", "Google", "Microsoft"],
            topics=["pricing", "market share"],
        )
        assert len(schema.urls) == 2
        assert len(schema.competitors) == 3
        assert len(schema.topics) == 2


# ---------------------------------------------------------------------------
# ProgressEvent schema
# ---------------------------------------------------------------------------

class TestProgressEvent:
    def test_valid_event_created(self):
        event = ProgressEvent(event="crawling", message="Started crawling.")
        assert event.event == "crawling"
        assert event.message == "Started crawling."
        assert event.detail is None

    def test_detail_accepted(self):
        event = ProgressEvent(event="complete", message="Done.", detail={"run_id": "abc"})
        assert event.detail == {"run_id": "abc"}

    def test_model_dump_includes_all_fields(self):
        event = ProgressEvent(event="error", message="Failed.", detail=None)
        dumped = event.model_dump()
        assert dumped["event"] == "error"
        assert dumped["message"] == "Failed."
        assert dumped["detail"] is None
