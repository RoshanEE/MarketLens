"""
Tests for the AI analysis pipeline.

get_llm_client() is patched so no real LLM calls are made.
_prepare_sources is patched in analyze_content tests to isolate JSON parsing logic.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ai_pipeline import _format_sources, analyze_content


# ---------------------------------------------------------------------------
# _format_sources  (pure function)
# ---------------------------------------------------------------------------

class TestFormatSources:
    def _source(self, url: str = "https://example.com", title: str = "Test", content: str = "Content here.") -> dict:
        return {"url": url, "title": title, "content": content}

    def test_single_source_contains_url(self):
        result = _format_sources([self._source(url="https://apple.com")])
        assert "https://apple.com" in result

    def test_single_source_contains_title(self):
        result = _format_sources([self._source(title="Apple Earnings")])
        assert "Apple Earnings" in result

    def test_single_source_contains_content(self):
        result = _format_sources([self._source(content="Revenue grew 10%.")])
        assert "Revenue grew 10%." in result

    def test_none_title_rendered_as_unknown(self):
        result = _format_sources([self._source(title=None)])
        assert "Unknown" in result

    def test_multiple_sources_all_included(self):
        sources = [
            self._source(url="https://a.com", content="Content A"),
            self._source(url="https://b.com", content="Content B"),
        ]
        result = _format_sources(sources)
        assert "https://a.com" in result
        assert "https://b.com" in result
        assert "Content A" in result
        assert "Content B" in result

    def test_sources_separated_by_delimiter(self):
        sources = [self._source(url="https://a.com"), self._source(url="https://b.com")]
        result = _format_sources(sources)
        assert "--- SOURCE ---" in result

    def test_empty_sources_returns_empty_string(self):
        assert _format_sources([]) == ""


# ---------------------------------------------------------------------------
# analyze_content  (patches LLM and _prepare_sources)
# ---------------------------------------------------------------------------

def _valid_analysis() -> dict:
    return {
        "themes": [
            {
                "title": "Market Growth",
                "summary": "Revenue increased.",
                "insights": [{"claim": "Revenue up 10%.", "source_url": "https://example.com", "source_title": None}],
            }
        ],
        "competitor_activities": [
            {
                "competitor": "Apple",
                "activities": [{"claim": "Apple launched X.", "source_url": "https://example.com", "source_title": None}],
            }
        ],
        "key_insights": [{"claim": "Key finding.", "source_url": "https://example.com", "source_title": None}],
    }


def _crawl_results() -> list[dict]:
    return [{"url": "https://example.com", "title": "Test Page", "content": "Some content."}]


@pytest.mark.asyncio
class TestAnalyzeContent:
    async def test_returns_parsed_analysis_dict(self):
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=json.dumps(_valid_analysis()))

        with (
            patch("app.services.ai_pipeline._prepare_sources", AsyncMock(return_value=_crawl_results())),
            patch("app.services.ai_pipeline.get_llm_client", return_value=mock_llm),
        ):
            result = await analyze_content(_crawl_results(), ["Apple"], ["pricing"], None)

        assert "themes" in result
        assert "competitor_activities" in result
        assert "key_insights" in result
        assert len(result["themes"]) == 1

    async def test_strips_markdown_code_block_before_parsing(self):
        raw = f"```json\n{json.dumps(_valid_analysis())}\n```"
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=raw)

        with (
            patch("app.services.ai_pipeline._prepare_sources", AsyncMock(return_value=_crawl_results())),
            patch("app.services.ai_pipeline.get_llm_client", return_value=mock_llm),
        ):
            result = await analyze_content(_crawl_results(), ["Apple"], ["pricing"], None)

        assert "themes" in result

    async def test_invalid_json_raises_value_error(self):
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value="not valid json at all")

        with (
            patch("app.services.ai_pipeline._prepare_sources", AsyncMock(return_value=_crawl_results())),
            patch("app.services.ai_pipeline.get_llm_client", return_value=mock_llm),
            pytest.raises(ValueError, match="malformed JSON"),
        ):
            await analyze_content(_crawl_results(), ["Apple"], ["pricing"], None)

    async def test_llm_called_with_competitors_and_topics_in_prompt(self):
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=json.dumps(_valid_analysis()))

        with (
            patch("app.services.ai_pipeline._prepare_sources", AsyncMock(return_value=_crawl_results())),
            patch("app.services.ai_pipeline.get_llm_client", return_value=mock_llm),
        ):
            await analyze_content(_crawl_results(), ["Apple", "Google"], ["pricing"], "Focus on Q4.")

        call_kwargs = mock_llm.complete.call_args
        prompt_text = call_kwargs.kwargs.get("user") or call_kwargs.args[2]
        assert "Apple" in prompt_text
        assert "Google" in prompt_text
        assert "pricing" in prompt_text
        assert "Focus on Q4." in prompt_text

    async def test_empty_competitors_and_topics_handled(self):
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=json.dumps(_valid_analysis()))

        with (
            patch("app.services.ai_pipeline._prepare_sources", AsyncMock(return_value=_crawl_results())),
            patch("app.services.ai_pipeline.get_llm_client", return_value=mock_llm),
        ):
            result = await analyze_content(_crawl_results(), [], [], None)

        assert "themes" in result

    async def test_context_included_in_prompt_when_provided(self):
        mock_llm = MagicMock()
        mock_llm.complete = AsyncMock(return_value=json.dumps(_valid_analysis()))

        with (
            patch("app.services.ai_pipeline._prepare_sources", AsyncMock(return_value=_crawl_results())),
            patch("app.services.ai_pipeline.get_llm_client", return_value=mock_llm),
        ):
            await analyze_content(_crawl_results(), ["Apple"], [], "Focus on EMEA region.")

        call_kwargs = mock_llm.complete.call_args
        prompt_text = call_kwargs.kwargs.get("user") or call_kwargs.args[2]
        assert "Focus on EMEA region." in prompt_text
