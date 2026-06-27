"""
Hallucination judge service (LLM-as-a-Judge).
For each claim in the analysis report, a separate LLM call verifies whether
the claim is directly supported by the source text. Claims that fail verification
are flagged with low confidence and a reasoning note.
"""

import asyncio
import json
import structlog
from app.core.config import get_settings
from app.services.llm_client import llm_complete

log = structlog.get_logger(__name__)
settings = get_settings()

JUDGE_SYSTEM = """You are a fact-checking judge. Your job is to determine whether a specific claim
is directly supported by a provided source text. Be strict: if the source text does not explicitly
state or clearly imply the claim, mark it as unsupported. Do not give benefit of the doubt."""

JUDGE_PROMPT = """SOURCE TEXT:
{source_text}

CLAIM TO VERIFY:
"{claim}"

Does the source text directly support this claim?

Respond with JSON only:
{{
  "supported": true or false,
  "confidence": 0.0 to 1.0,
  "reasoning": "One sentence explanation"
}}"""

CONFIDENCE_THRESHOLD = 0.6


async def _judge_single_claim(
    claim: str,
    source_url: str,
    source_lookup: dict[str, str],
) -> dict:
    """Verify one claim against its source. Returns verdict dict."""
    source_text = source_lookup.get(source_url, "")

    if not source_text:
        return {
            "supported": False,
            "confidence": 0.0,
            "reasoning": "Source content unavailable for verification.",
        }

    truncated = source_text[:6000]

    raw = await llm_complete(
        model=settings.judge_model,
        system=JUDGE_SYSTEM,
        user=JUDGE_PROMPT.format(source_text=truncated, claim=claim),
        max_tokens=256,
    )
    raw = raw.strip()

    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {"supported": False, "confidence": 0.0, "reasoning": "Judge returned unparseable response."}


async def _judge_insights(
    insights: list[dict],
    source_lookup: dict[str, str],
) -> list[dict]:
    """Run hallucination checks on a list of insight dicts concurrently."""
    verdicts = await asyncio.gather(
        *[_judge_single_claim(ins["claim"], ins.get("source_url", ""), source_lookup) for ins in insights]
    )
    return [
        {
            **insight,
            "confidence": v.get("confidence", 0.0),
            "verified": v.get("supported", False) and v.get("confidence", 0.0) >= CONFIDENCE_THRESHOLD,
            "judge_reasoning": v.get("reasoning"),
        }
        for insight, v in zip(insights, verdicts)
    ]


async def run_hallucination_check(
    analysis: dict,
    crawl_results: list[dict],
) -> dict:
    """
    Verify every claim in the analysis report against its source.
    Returns the analysis dict with confidence scores and verification flags added.
    """
    source_lookup: dict[str, str] = {
        r["url"]: (r["content"] or "") for r in crawl_results if r.get("content")
    }

    all_theme_insights = [ins for theme in analysis.get("themes", []) for ins in theme.get("insights", [])]
    all_competitor_insights = [ins for ca in analysis.get("competitor_activities", []) for ins in ca.get("activities", [])]
    key_insights = analysis.get("key_insights", [])

    log.info(
        "judge.start",
        theme_claims=len(all_theme_insights),
        competitor_claims=len(all_competitor_insights),
        key_claims=len(key_insights),
    )

    verified_themes_flat, verified_competitors_flat, verified_key = await asyncio.gather(
        _judge_insights(all_theme_insights, source_lookup),
        _judge_insights(all_competitor_insights, source_lookup),
        _judge_insights(key_insights, source_lookup),
    )

    # Re-attach verified insights back into themes
    theme_idx = 0
    verified_themes = []
    for theme in analysis.get("themes", []):
        count = len(theme.get("insights", []))
        verified_themes.append({**theme, "insights": verified_themes_flat[theme_idx: theme_idx + count]})
        theme_idx += count

    # Re-attach into competitor activities
    ca_idx = 0
    verified_competitors = []
    for ca in analysis.get("competitor_activities", []):
        count = len(ca.get("activities", []))
        verified_competitors.append({**ca, "activities": verified_competitors_flat[ca_idx: ca_idx + count]})
        ca_idx += count

    all_confidences = (
        [i["confidence"] for i in verified_themes_flat]
        + [i["confidence"] for i in verified_competitors_flat]
        + [i["confidence"] for i in verified_key]
    )
    overall_confidence = round(sum(all_confidences) / len(all_confidences), 3) if all_confidences else None
    verified_count = sum(1 for c in all_confidences if c >= CONFIDENCE_THRESHOLD)

    hallucination_results = {
        "total_claims": len(all_confidences),
        "verified_claims": verified_count,
        "unverified_claims": len(all_confidences) - verified_count,
        "overall_confidence": overall_confidence,
        "confidence_threshold": CONFIDENCE_THRESHOLD,
    }

    log.info("judge.complete", **hallucination_results)

    return {
        "themes": verified_themes,
        "competitor_activities": verified_competitors,
        "key_insights": verified_key,
        "hallucination_results": hallucination_results,
        "overall_confidence": overall_confidence,
    }
