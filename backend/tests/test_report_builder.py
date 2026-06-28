"""
Tests for the pure utility functions in report_builder.

_make_event and _detect_changes have no external dependencies and need no mocking.
"""

import json
import pytest

from app.services.report_builder import _make_event, _detect_changes


# ---------------------------------------------------------------------------
# _make_event
# ---------------------------------------------------------------------------

class TestMakeEvent:
    def _parse(self, sse: str) -> dict:
        """Strip the 'data: ' prefix and trailing newlines, then parse JSON."""
        assert sse.startswith("data: "), "SSE line must start with 'data: '"
        return json.loads(sse.removeprefix("data: ").strip())

    def test_output_starts_with_data_prefix(self):
        result = _make_event("crawling", "Started")
        assert result.startswith("data: ")

    def test_output_ends_with_double_newline(self):
        result = _make_event("crawling", "Started")
        assert result.endswith("\n\n")

    def test_event_field_is_preserved(self):
        payload = self._parse(_make_event("analyzing", "Running"))
        assert payload["event"] == "analyzing"

    def test_message_field_is_preserved(self):
        payload = self._parse(_make_event("complete", "Done successfully"))
        assert payload["message"] == "Done successfully"

    def test_detail_included_when_provided(self):
        detail = {"run_id": "abc-123", "changes": []}
        payload = self._parse(_make_event("complete", "Done", detail=detail))
        assert payload["detail"] == detail

    def test_detail_is_none_when_omitted(self):
        payload = self._parse(_make_event("crawling", "Started"))
        assert payload["detail"] is None

    def test_all_event_types_produce_valid_json(self):
        for event_type in ("crawling", "analyzing", "judging", "complete", "error"):
            payload = self._parse(_make_event(event_type, f"{event_type} message"))
            assert payload["event"] == event_type

    def test_nested_detail_serialized_correctly(self):
        detail = {"failed": ["https://a.com", "https://b.com"], "count": 2}
        payload = self._parse(_make_event("crawling", "Partial", detail=detail))
        assert payload["detail"]["failed"] == ["https://a.com", "https://b.com"]
        assert payload["detail"]["count"] == 2


# ---------------------------------------------------------------------------
# _detect_changes
# ---------------------------------------------------------------------------

class TestDetectChanges:
    def test_new_url_produces_new_url_change(self):
        changes = _detect_changes(
            current_hashes={"https://example.com": "abc123"},
            previous_hashes={},
        )
        assert changes == [{"url": "https://example.com", "type": "new_url"}]

    def test_changed_hash_produces_content_changed(self):
        changes = _detect_changes(
            current_hashes={"https://example.com": "new_hash"},
            previous_hashes={"https://example.com": "old_hash"},
        )
        assert changes == [{"url": "https://example.com", "type": "content_changed"}]

    def test_identical_hash_produces_no_change(self):
        changes = _detect_changes(
            current_hashes={"https://example.com": "same_hash"},
            previous_hashes={"https://example.com": "same_hash"},
        )
        assert changes == []

    def test_empty_current_hashes_produces_no_changes(self):
        changes = _detect_changes(
            current_hashes={},
            previous_hashes={"https://example.com": "abc123"},
        )
        assert changes == []

    def test_mixed_new_changed_and_unchanged_urls(self):
        changes = _detect_changes(
            current_hashes={
                "https://new.com": "hash_n",       # new
                "https://changed.com": "hash_new",  # changed
                "https://same.com": "hash_s",       # unchanged
            },
            previous_hashes={
                "https://changed.com": "hash_old",
                "https://same.com": "hash_s",
            },
        )

        change_map = {c["url"]: c["type"] for c in changes}
        assert change_map["https://new.com"] == "new_url"
        assert change_map["https://changed.com"] == "content_changed"
        assert "https://same.com" not in change_map

    def test_both_empty_produces_no_changes(self):
        assert _detect_changes({}, {}) == []

    def test_multiple_new_urls_all_reported(self):
        urls = {f"https://url{i}.com": f"hash{i}" for i in range(5)}
        changes = _detect_changes(current_hashes=urls, previous_hashes={})
        assert len(changes) == 5
        assert all(c["type"] == "new_url" for c in changes)
