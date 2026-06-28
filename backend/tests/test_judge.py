"""
Tests for the hallucination-judge service.

get_llm_client() is patched at the app.services.judge module level so no
real LLM calls are made.
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.judge import (
    _judge_single_claim,
    _judge_insights,
    run_hallucination_check,
    CONFIDENCE_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _mock_llm(response: str) -> MagicMock:
    client = MagicMock()
    client.complete = AsyncMock(return_value=response)
    return client


def _verdict(supported: bool = True, confidence: float = 0.9, reasoning: str = "OK.") -> str:
    return json.dumps({"supported": supported, "confidence": confidence, "reasoning": reasoning})


# ---------------------------------------------------------------------------
# _judge_single_claim
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestJudgeSingleClaim:
    async def test_missing_source_returns_unsupported_without_llm_call(self):
        with patch("app.services.judge.get_llm_client") as mock_get:
            result = await _judge_single_claim(
                claim="Apple is great",
                source_url="https://example.com",
                source_lookup={},  # URL not present
            )
            mock_get.assert_not_called()

        assert result["supported"] is False
        assert result["confidence"] == 0.0
        assert "unavailable" in result["reasoning"].lower()

    async def test_supported_verdict_parsed_correctly(self):
        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(True, 0.95))):
            result = await _judge_single_claim(
                claim="Apple revenue grew",
                source_url="https://example.com",
                source_lookup={"https://example.com": "Apple revenue grew by 10% last year."},
            )

        assert result["supported"] is True
        assert result["confidence"] == 0.95

    async def test_unsupported_verdict_parsed_correctly(self):
        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(False, 0.1, "Not found."))):
            result = await _judge_single_claim(
                claim="Apple went bankrupt",
                source_url="https://example.com",
                source_lookup={"https://example.com": "Apple had record profits."},
            )

        assert result["supported"] is False
        assert result["confidence"] == 0.1

    async def test_markdown_code_block_stripped_before_parse(self):
        raw = f"```json\n{_verdict(True, 0.8)}\n```"
        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(raw)):
            result = await _judge_single_claim(
                claim="Some claim",
                source_url="https://example.com",
                source_lookup={"https://example.com": "Some source text about the claim."},
            )

        assert result["supported"] is True
        assert result["confidence"] == 0.8

    async def test_invalid_json_returns_fallback_unsupported(self):
        with patch("app.services.judge.get_llm_client", return_value=_mock_llm("not valid json")):
            result = await _judge_single_claim(
                claim="Some claim",
                source_url="https://example.com",
                source_lookup={"https://example.com": "Some source text."},
            )

        assert result["supported"] is False
        assert result["confidence"] == 0.0
        assert "unparseable" in result["reasoning"].lower()

    async def test_long_source_text_passed_to_llm_in_full(self):
        """Full source text is forwarded to the LLM — no truncation applied."""
        long_source = "x" * 10_000
        mock_llm = _mock_llm(_verdict(True, 0.7))
        with patch("app.services.judge.get_llm_client", return_value=mock_llm):
            result = await _judge_single_claim(
                claim="Some claim",
                source_url="https://example.com",
                source_lookup={"https://example.com": long_source},
            )

        call_kwargs = mock_llm.complete.call_args
        assert long_source in str(call_kwargs)
        assert result["supported"] is True


# ---------------------------------------------------------------------------
# _judge_insights
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestJudgeInsights:
    def _make_insight(self, claim: str, url: str = "https://example.com") -> dict:
        return {"claim": claim, "source_url": url}

    async def test_annotates_insights_with_verified_flag(self):
        source_lookup = {"https://example.com": "Apple grew revenue."}
        insights = [self._make_insight("Apple grew revenue.")]

        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(True, 0.9))):
            results = await _judge_insights(insights, source_lookup)

        assert len(results) == 1
        assert results[0]["verified"] is True
        assert results[0]["confidence"] == 0.9
        assert "judge_reasoning" in results[0]

    async def test_below_threshold_confidence_sets_verified_false(self):
        source_lookup = {"https://example.com": "Some text."}
        insights = [self._make_insight("A borderline claim.")]
        low_confidence = CONFIDENCE_THRESHOLD - 0.1

        with patch(
            "app.services.judge.get_llm_client",
            return_value=_mock_llm(_verdict(True, low_confidence)),
        ):
            results = await _judge_insights(insights, source_lookup)

        assert results[0]["verified"] is False

    async def test_at_threshold_confidence_sets_verified_true(self):
        source_lookup = {"https://example.com": "Some text."}
        insights = [self._make_insight("A threshold claim.")]

        with patch(
            "app.services.judge.get_llm_client",
            return_value=_mock_llm(_verdict(True, CONFIDENCE_THRESHOLD)),
        ):
            results = await _judge_insights(insights, source_lookup)

        assert results[0]["verified"] is True

    async def test_multiple_insights_all_annotated(self):
        source_lookup = {"https://a.com": "Content A.", "https://b.com": "Content B."}
        insights = [
            self._make_insight("Claim A", "https://a.com"),
            self._make_insight("Claim B", "https://b.com"),
        ]

        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(True, 0.8))):
            results = await _judge_insights(insights, source_lookup)

        assert len(results) == 2
        assert all("verified" in r for r in results)
        assert all("confidence" in r for r in results)

    async def test_unsupported_confidence_is_inverted(self):
        """When supported=False, effective confidence = 1 - raw so 90% sure it's wrong → 10% credibility."""
        source_lookup = {"https://example.com": "Apple had record profits."}
        insights = [self._make_insight("Apple went bankrupt.")]

        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(False, 0.9, "Not found."))):
            results = await _judge_insights(insights, source_lookup)

        assert results[0]["verified"] is False
        assert abs(results[0]["confidence"] - 0.1) < 0.001

    async def test_unsupported_with_full_certainty_gives_zero_confidence(self):
        """When supported=False and confidence=1.0, effective confidence = 0."""
        source_lookup = {"https://example.com": "Apple had record profits."}
        insights = [self._make_insight("Apple went bankrupt.")]

        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(False, 1.0, "Clearly wrong."))):
            results = await _judge_insights(insights, source_lookup)

        assert results[0]["verified"] is False
        assert results[0]["confidence"] == 0.0

    async def test_empty_insights_returns_empty_list(self):
        with patch("app.services.judge.get_llm_client") as mock_get:
            results = await _judge_insights([], {})

        assert results == []
        mock_get.assert_not_called()


# ---------------------------------------------------------------------------
# run_hallucination_check
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestRunHallucinationCheck:
    def _make_analysis(
        self,
        theme_claims: int = 1,
        competitor_claims: int = 1,
        key_claims: int = 1,
    ) -> dict:
        url = "https://example.com"
        claim = lambda i: {"claim": f"Claim {i}", "source_url": url, "source_title": None}
        return {
            "themes": [{"title": "Theme", "summary": "Summary", "insights": [claim(i) for i in range(theme_claims)]}],
            "competitor_activities": [{"competitor": "Apple", "activities": [claim(i) for i in range(competitor_claims)]}],
            "key_insights": [claim(i) for i in range(key_claims)],
        }

    def _crawl_results(self) -> list[dict]:
        return [{"url": "https://example.com", "content": "Relevant source content."}]

    async def test_returns_verified_structure_with_all_sections(self):
        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(True, 0.85))):
            result = await run_hallucination_check(self._make_analysis(), self._crawl_results())

        assert "themes" in result
        assert "competitor_activities" in result
        assert "key_insights" in result
        assert "hallucination_results" in result
        assert "overall_confidence" in result

    async def test_hallucination_results_totals_are_correct(self):
        # 1 theme claim + 1 competitor claim + 1 key claim = 3 total
        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(True, 0.9))):
            result = await run_hallucination_check(self._make_analysis(), self._crawl_results())

        hr = result["hallucination_results"]
        assert hr["total_claims"] == 3
        assert hr["verified_claims"] + hr["unverified_claims"] == hr["total_claims"]

    async def test_overall_confidence_is_average_of_all_claims(self):
        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(True, 0.6))):
            result = await run_hallucination_check(self._make_analysis(), self._crawl_results())

        assert abs(result["overall_confidence"] - 0.6) < 0.01

    async def test_theme_insights_reattached_in_original_order(self):
        """Insights should be put back into the correct theme after flat verification."""
        analysis = {
            "themes": [
                {"title": "T1", "summary": "S1", "insights": [{"claim": "A", "source_url": "https://example.com", "source_title": None}]},
                {"title": "T2", "summary": "S2", "insights": [{"claim": "B", "source_url": "https://example.com", "source_title": None}]},
            ],
            "competitor_activities": [],
            "key_insights": [],
        }

        with patch("app.services.judge.get_llm_client", return_value=_mock_llm(_verdict(True, 0.8))):
            result = await run_hallucination_check(analysis, self._crawl_results())

        assert result["themes"][0]["title"] == "T1"
        assert result["themes"][1]["title"] == "T2"
        assert result["themes"][0]["insights"][0]["claim"] == "A"
        assert result["themes"][1]["insights"][0]["claim"] == "B"

    async def test_crawl_results_without_content_excluded_from_source_lookup(self):
        """URLs with no content should produce unsupported verdicts (no source available)."""
        analysis = {
            "themes": [],
            "competitor_activities": [],
            "key_insights": [{"claim": "Some claim", "source_url": "https://example.com", "source_title": None}],
        }
        crawl_results = [{"url": "https://example.com", "content": None}]  # no content

        with patch("app.services.judge.get_llm_client") as mock_get:
            result = await run_hallucination_check(analysis, crawl_results)
            mock_get.assert_not_called()  # no source → no LLM call

        assert result["key_insights"][0]["verified"] is False
        assert result["key_insights"][0]["confidence"] == 0.0

    async def test_empty_analysis_returns_none_overall_confidence(self):
        analysis = {"themes": [], "competitor_activities": [], "key_insights": []}

        with patch("app.services.judge.get_llm_client"):
            result = await run_hallucination_check(analysis, [])

        assert result["overall_confidence"] is None
        assert result["hallucination_results"]["total_claims"] == 0
