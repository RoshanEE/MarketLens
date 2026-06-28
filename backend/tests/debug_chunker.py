"""
Chunker debug script -- visualize splitting, scoring, and selection.

Edit the INPUT section below, then run:

    cd backend
    python tests/debug_chunker.py

Two modes:
  URL mode  -- set URL to a web address; the page is crawled first and its
               extracted text becomes the content. CONTENT is ignored.
  Text mode -- leave URL empty ("") and paste your text into CONTENT.

Set USE_REAL_LLM = True to call the LLM for summaries (requires a valid .env).
Set USE_REAL_LLM = False to use the first sentence of each chunk as a stand-in
summary so you can explore splitting and scoring without any API key.
"""

import asyncio
import os
import re
import sys

# Force UTF-8 output so crawled content with non-ASCII characters prints safely
# on Windows (which defaults to cp1252).
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ── Add backend/ to path so app.* imports resolve ─────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Required env vars (only needed when USE_REAL_LLM = True) ──────────────────
os.environ.setdefault("SUPABASE_URL", "https://placeholder.supabase.co")
os.environ.setdefault("SUPABASE_ANON_KEY", "placeholder")
os.environ.setdefault("SUPABASE_SERVICE_ROLE_KEY", "placeholder")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost/db")

# ==============================================================================
# INPUTS -- edit these
# ==============================================================================

# Set a URL to crawl it live. Leave empty ("") to use CONTENT below instead.
URL = ""

CONTENT = """
Apple unveiled its latest lineup of MacBook Pro laptops powered by the new M4 chip,
claiming up to 40% faster performance than the previous generation. The company also
announced a new 14-inch MacBook Pro starting at $1,599, a $200 price reduction from
the M3 model. Apple CFO Luca Maestri highlighted strong enterprise adoption as a key
driver of Mac revenue growth.

Google responded by announcing expanded Chromebook Plus specifications, emphasizing
AI-powered features built directly into ChromeOS. The company partnered with Lenovo
and HP to release new devices starting at $399, targeting the education and SMB
segments. Google's VP of ChromeOS stated that the AI features give Chromebooks a
significant advantage in productivity workflows.

Microsoft Surface division reported a 12% year-over-year revenue increase, driven
by the Surface Pro 11 and Surface Laptop 7 which now feature Snapdragon X Elite
processors. The company is aggressively courting enterprise customers with a bundled
Microsoft 365 Copilot offering for new Surface purchases.

In the broader PC market, analysts from IDC reported a 4.2% global shipment increase
in Q3, the first positive growth in six consecutive quarters. Lenovo maintained its
position as the market leader with 24% market share, followed by HP at 21% and Dell
at 18%. Apple grew its market share by 1.2 percentage points to reach 9.1%.

Supply chain constraints for advanced semiconductors continue to affect production
timelines. TSMC announced plans to expand its Arizona fab capacity by 2026, which
analysts expect will ease pricing pressure on premium laptop components. However,
short-term component costs remain elevated, particularly for OLED display panels.

The consumer segment showed uneven recovery, with premium devices above $1,500
showing stronger demand than mid-range products. Back-to-school promotions from
major retailers drove a short-term sales spike in August, but September saw a return
to more modest growth rates. Analysts expect holiday season demand to be cautiously
optimistic given continued macroeconomic uncertainty.

IT decision makers surveyed by Gartner cited battery life and security as the top
two purchasing criteria for enterprise laptops, above performance and price. This
has benefited ARM-based devices like Apple Silicon Macs and Snapdragon-powered
Surface devices, which consistently outperform x86 competitors on battery benchmarks.
"""

COMPETITORS = ["Novartis"]
# COMPETITORS = ["Apple", "Google", "Microsoft", "Lenovo"]
TOPICS = ["drug", "pricing", "acquisition"]

CHUNK_SIZE = 600   # target characters per chunk (lower = more chunks)
TOP_K = 8          # how many chunks to keep
MIN_RELEVANCE = 2.0  # chunks scoring below this (0-10) are treated as off-topic and dropped

# Set True to call the real LLM for summaries (needs valid API keys in .env).
# Set False to use the first sentence of each chunk as the summary — fast, no API.
USE_REAL_LLM = True

# LLM model used for summarization (only relevant when USE_REAL_LLM = True)
SUMMARIZATION_MODEL = "gpt-4.1-mini"

# ==============================================================================


def _separator(char: str = "-", width: int = 72) -> str:
    return char * width


def _print_chunk(index: int, chunk: str, summary: str, score: float, selected: bool) -> None:
    tag = "  [SELECTED]" if selected else "  [dropped] "
    filled = round(score)
    bar = "#" * filled + "." * (10 - filled)
    print(f"\nChunk {index + 1}{tag}  relevance={score:.1f}/10  {bar}  ({len(chunk)} chars)")
    print(_separator("."))
    preview = chunk if len(chunk) <= 300 else chunk[:297] + "..."
    print(preview)
    print(_separator("."))
    print(f"  Summary: {summary}")


async def _get_summaries(chunks: list[str], model: str) -> list[tuple[str, float]]:
    if not USE_REAL_LLM:
        from app.services.chunker import ContentChunker
        max_terms = max(1, len(COMPETITORS + TOPICS))
        result = []
        for chunk in chunks:
            summary = chunk.split(".")[0].strip() + "."
            hits = ContentChunker.score(summary, COMPETITORS, TOPICS)
            relevance = round(hits / max_terms * 10.0, 1)
            result.append((summary, relevance))
        return result

    from app.services.llm_client import get_llm_client
    from app.services.chunker import ContentChunker

    llm = get_llm_client()
    chunker = ContentChunker(llm=llm, chunk_size=CHUNK_SIZE, top_k=TOP_K)
    return await chunker.summarize(chunks, model, COMPETITORS, TOPICS)


async def _resolve_content() -> tuple[str, str]:
    """
    Returns (content, source_label).
    If URL is set, crawls it and returns the extracted text.
    Otherwise returns the CONTENT constant.
    """
    if not URL.strip():
        return CONTENT.strip(), "inline CONTENT"

    from app.services.crawler import crawl_url

    print(f"  Crawling {URL} ...")
    result = await crawl_url(URL.strip())

    if result.status == "failed":
        print(f"\n  ERROR: Crawl failed -- {result.error}")
        print("  Fix the URL or fall back to setting CONTENT manually.")
        raise SystemExit(1)

    title = result.title or "untitled"
    content = result.content or ""
    print(f"  Status  : {result.status}")
    print(f"  Title   : {title}")
    print(f"  Raw len : {len(content)} chars")
    return content, f"crawled URL: {URL.strip()} ({title})"


async def main() -> None:
    from app.services.chunker import ContentChunker, _MIN_CHUNK

    # Dummy LLM -- only used when USE_REAL_LLM=False (summarize is bypassed)
    class _NoLLM:
        async def complete(self, **_):
            return "[]"

    chunker = ContentChunker(
        llm=_NoLLM(),  # type: ignore[arg-type]
        chunk_size=CHUNK_SIZE,
        top_k=TOP_K,
        min_relevance=MIN_RELEVANCE,
    )

    print(_separator("="))
    print("  CHUNKER DEBUG")
    print(_separator("="))
    print(f"  Competitors   : {COMPETITORS}")
    print(f"  Topics        : {TOPICS}")
    print(f"  chunk_size    : {CHUNK_SIZE}  |  top_k : {TOP_K}  |  min_chunk : {_MIN_CHUNK}")
    print(f"  min_relevance : {MIN_RELEVANCE}/10  (chunks scoring below this are dropped as off-topic)")
    print(f"  Scoring       : {'LLM semantic (' + SUMMARIZATION_MODEL + ')' if USE_REAL_LLM else 'keyword-based (no LLM)'}")
    print()

    content, source_label = await _resolve_content()

    print(f"  Source      : {source_label}")
    print(f"  Content len : {len(content)} chars")

    # ── Step 0: Content structure diagnostic ──────────────────────────────────
    double_nl = content.count("\n\n")
    single_nl = content.count("\n")
    separator_mode = "double-newline (\\n\\n)" if double_nl > 0 else "single-newline (\\n) fallback"
    raw_para_count = len([p for p in (re.split(r"\n{2,}", content) if double_nl > 0 else content.split("\n")) if p.strip()])
    print(f"  Paragraph separator : {separator_mode}")
    print(f"  Raw paragraphs      : {raw_para_count}  (before size filtering)")
    print(f"  double-newlines     : {double_nl}  |  single-newlines : {single_nl}")

    # ── Step 1: Split ──────────────────────────────────────────────────────────
    print(f"\n{_separator('=')}")
    print("  STEP 1 - SPLIT")
    print(_separator("="))

    chunks = chunker.split(content)
    print(f"  {len(chunks)} chunk(s) produced  (paragraphs < {_MIN_CHUNK} chars discarded, short ones merged up to {CHUNK_SIZE} chars)\n")

    if not chunks:
        print("  No chunks produced. Try longer content or a smaller CHUNK_SIZE.")
        return

    if len(chunks) <= TOP_K:
        print(f"  Only {len(chunks)} chunk(s) produced -- <= top_k={TOP_K}.")
        print("  select() would return the content as-is (no LLM calls made).")
        print("  Showing chunks anyway:\n")

    for i, chunk in enumerate(chunks):
        print(f"  Chunk {i + 1}  ({len(chunk)} chars)")
        preview = chunk if len(chunk) <= 200 else chunk[:197] + "..."
        print(f"  {preview}\n")

    # ── Step 2: Summarize + score ──────────────────────────────────────────────
    score_source = "LLM semantic scoring" if USE_REAL_LLM else "keyword scoring (no LLM)"
    print(_separator("="))
    print(f"  STEP 2 - SUMMARIZE + RELEVANCE SCORE  ({score_source})")
    print(_separator("="))

    summaries_and_scores = await _get_summaries(chunks, SUMMARIZATION_MODEL)
    summaries = [s for s, _ in summaries_and_scores]
    scores = [sc for _, sc in summaries_and_scores]

    print(f"  {len(summaries)} summar{'y' if len(summaries) == 1 else 'ies'} generated\n")
    for i, (summary, score) in enumerate(summaries_and_scores):
        filled = round(score)
        bar = "#" * filled + "." * (10 - filled)
        print(f"  [{i + 1}] {score:.1f}/10  {bar}  {summary}")

    # -- Step 3: Select --------------------------------------------------------
    print(f"\n{_separator('=')}")
    print(f"  STEP 3 - SELECT  (min_relevance={MIN_RELEVANCE}/10, top_k={TOP_K})")
    print(_separator("="))

    above = [i for i, sc in enumerate(scores) if sc >= MIN_RELEVANCE]

    if not above:
        print(f"  No chunks scored >= {MIN_RELEVANCE} -- page is off-topic, select() would return \"\".")
        top_indices = []
    elif len(above) <= TOP_K:
        top_indices = above
        print(f"  {len(above)} chunk(s) above threshold (all fit within top_k={TOP_K}): chunks {[i + 1 for i in top_indices]}")
    else:
        ranked = sorted(above, key=lambda i: scores[i], reverse=True)
        top_indices = sorted(ranked[:TOP_K])
        print(f"  {len(above)} chunks above threshold, keeping top {TOP_K} by score (document order): chunks {[i + 1 for i in top_indices]}")

    selected_set = set(top_indices)

    print()
    for i, (chunk, summary, score) in enumerate(zip(chunks, summaries, scores)):
        _print_chunk(i, chunk, summary, score, selected=i in selected_set)

    # -- Final output ----------------------------------------------------------
    selected_text = "\n\n".join(chunks[i] for i in top_indices)
    print(f"\n{_separator('=')}")
    print("  FINAL OUTPUT")
    print(_separator("="))
    if not top_indices:
        print("  (empty -- all chunks were below the relevance threshold)")
    else:
        print(f"  {len(top_indices)} of {len(chunks)} chunks selected  ({len(selected_text)} of {len(content)} chars kept)\n")
        print(selected_text)
    print(f"\n{_separator('=')}")


if __name__ == "__main__":
    asyncio.run(main())
