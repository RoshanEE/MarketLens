"""
AI analysis pipeline.
Sends crawled content to Claude to extract structured market intelligence:
themes, competitor activities, and source-grounded insights.
"""

import json
import structlog
from app.core.config import get_settings
from app.services.llm_client import llm_complete

log = structlog.get_logger(__name__)
settings = get_settings()

# Limit content per URL to avoid hitting context limits (approx 3000 tokens each)
MAX_CONTENT_CHARS = 12_000

SYSTEM_PROMPT = """You are a market intelligence analyst. Your task is to extract structured insights
from web content about competitor activity and market trends. You produce precise, source-grounded
analysis. Every claim you make must be directly supported by the provided source text.
Do NOT invent or extrapolate information not present in the sources."""

ANALYSIS_PROMPT_TEMPLATE = """
Analyze the following web content to extract market intelligence on these topics:

COMPETITORS TO TRACK: {competitors}
TOPICS OF INTEREST: {topics}
ADDITIONAL CONTEXT: {context}

SOURCE CONTENT:
{sources}

Return a JSON object with this exact structure:
{{
  "themes": [
    {{
      "title": "Theme title (concise)",
      "summary": "2-3 sentence summary of this theme",
      "insights": [
        {{
          "claim": "Specific factual claim",
          "source_url": "URL this came from",
          "source_title": "Page title or null"
        }}
      ]
    }}
  ],
  "competitor_activities": [
    {{
      "competitor": "Competitor name",
      "activities": [
        {{
          "claim": "Specific activity or announcement",
          "source_url": "URL",
          "source_title": "Page title or null"
        }}
      ]
    }}
  ],
  "key_insights": [
    {{
      "claim": "High-priority insight",
      "source_url": "URL",
      "source_title": "Page title or null"
    }}
  ]
}}

Rules:
- Only include competitors explicitly mentioned in the sources.
- Only include themes with at least one source-backed insight.
- Keep claims short (1-2 sentences) and factual.
- Use the exact URL string from the source metadata.
"""


def _format_sources(crawl_results: list[dict]) -> str:
    parts = []
    for r in crawl_results:
        content = (r["content"] or "")[:MAX_CONTENT_CHARS]
        parts.append(
            f"--- SOURCE ---\nURL: {r['url']}\nTITLE: {r.get('title') or 'Unknown'}\n\n{content}\n"
        )
    return "\n".join(parts)


async def analyze_content(
    crawl_results: list[dict],
    competitors: list[str],
    topics: list[str],
    context: str | None,
) -> dict:
    """
    Send crawled content to Claude for structured analysis.
    Returns the parsed JSON analysis dict.
    """
    sources_text = _format_sources(crawl_results)
    prompt = ANALYSIS_PROMPT_TEMPLATE.format(
        competitors=", ".join(competitors) if competitors else "None specified",
        topics=", ".join(topics) if topics else "None specified",
        context=context or "None",
        sources=sources_text,
    )

    log.info("ai_pipeline.analyze_start", model=settings.analysis_model, source_count=len(crawl_results))

    raw = await llm_complete(
        model=settings.analysis_model,
        system=SYSTEM_PROMPT,
        user=prompt,
        max_tokens=4096,
    )
    raw = raw.strip()

    # Strip markdown code fences if the model wrapped the JSON
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        result = json.loads(raw)
    except json.JSONDecodeError as exc:
        log.error("ai_pipeline.json_parse_error", error=str(exc), raw=raw[:500])
        raise ValueError(f"AI returned malformed JSON: {exc}") from exc

    log.info("ai_pipeline.analyze_complete", themes=len(result.get("themes", [])))
    return result
