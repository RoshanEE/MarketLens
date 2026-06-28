"""
Content chunker for handling long web pages.

Splits raw extracted text into paragraph-based chunks, generates a one-sentence
summary and a relevance score per chunk via a single LLM call, and returns the
top-K most relevant chunks in their original document order.

Scoring is done by the LLM in the same call as summarisation — this gives
semantic relevance (e.g. "cost reduction" matches "pricing") rather than the
crude keyword overlap that a post-hoc keyword count would provide.

This ensures the most relevant content reaches the main analysis LLM regardless of where it appears in the page.
"""

import json
import re
import structlog

from app.services.llm_client import LLMClient

log = structlog.get_logger(__name__)

_CHUNK_SIZE = 800    # target chars per chunk
_MIN_CHUNK = 150     # discard chunks shorter than this (nav fragments, captions)
_TOP_K = 8           # chunks to keep per URL
_MIN_RELEVANCE = 2.0 # chunks scoring below this (0-10) are considered off-topic

_SUMMARIZE_SYSTEM = (
    "You are a document analyst. For each text chunk, write a one-sentence summary "
    "and score its relevance to the provided research query."
)
_SUMMARIZE_PROMPT = """\
Research query:
Competitors: {competitors}
Topics: {topics}

For each of the following {n} numbered chunks return a JSON array of objects with:
  "summary"   - one concise sentence describing the chunk
  "relevance" - float 0.0 to 10.0 scoring how relevant the chunk is to the research query
                (0.0 = completely off-topic, 10.0 = directly addresses the query)

CHUNKS:
{chunks}

Return a JSON array of exactly {n} objects in the same order, nothing else."""


class ContentChunker:
    """
    Splits long document content into chunks, selects the most relevant ones
    for a given research query, and returns them rejoined in original order.
    """

    def __init__(
        self,
        llm: LLMClient,
        chunk_size: int = _CHUNK_SIZE,
        top_k: int = _TOP_K,
        min_relevance: float = _MIN_RELEVANCE,
    ) -> None:
        self.llm = llm
        self.chunk_size = chunk_size
        self.top_k = top_k
        self.min_relevance = min_relevance

    def split(self, content: str) -> list[str]:
        """
        Split content on paragraph boundaries, merging short paragraphs
        into the same chunk until chunk_size is reached.

        Tries double-newline splits first (standard HTML-extracted text). If
        that yields only one paragraph the content likely uses single newlines
        (common with trafilatura output on some pages), so falls back to
        splitting on single newlines instead.
        """
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", content) if p.strip()]
        if len(paragraphs) <= 1:
            paragraphs = [p.strip() for p in content.split("\n") if p.strip()]

        chunks: list[str] = []
        current = ""

        for para in paragraphs:
            if not current:
                current = para
            elif len(current) + len(para) + 2 <= self.chunk_size:
                current = current + "\n\n" + para
            else:
                if len(current) >= _MIN_CHUNK:
                    chunks.append(current)
                current = para

        if current and len(current) >= _MIN_CHUNK:
            chunks.append(current)

        return chunks

    async def summarize(
        self,
        chunks: list[str],
        model: str,
        competitors: list[str] | None = None,
        topics: list[str] | None = None,
    ) -> list[tuple[str, float]]:
        """
        Generate one-sentence summaries and relevance scores for all chunks in
        a single LLM call. The LLM scores each chunk semantically against the
        research query, so synonyms and paraphrases are handled correctly.

        Falls back to (first_sentence, 0.0) per chunk if the response cannot
        be parsed.
        """
        if not chunks:
            return []

        competitors = competitors or []
        topics = topics or []

        formatted = "\n\n".join(f"[{i + 1}] {chunk}" for i, chunk in enumerate(chunks))
        raw = await self.llm.complete(
            model=model,
            system=_SUMMARIZE_SYSTEM,
            user=_SUMMARIZE_PROMPT.format(
                n=len(chunks),
                competitors=", ".join(competitors) if competitors else "None",
                topics=", ".join(topics) if topics else "None",
                chunks=formatted,
            ),
            max_tokens=max(256, len(chunks) * 100),
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            parsed = json.loads(raw)
            if isinstance(parsed, list) and len(parsed) == len(chunks):
                return [
                    (str(item.get("summary", "")), float(item.get("relevance", 0.0)))
                    for item in parsed
                ]
            log.warning("chunker.summarize_length_mismatch", expected=len(chunks), got=len(parsed))
        except (json.JSONDecodeError, ValueError, TypeError, AttributeError):
            log.warning("chunker.summarize_parse_error", raw=raw[:300])

        # Fallback: first sentence + score 0.0 for each chunk
        return [(chunk.split(".")[0].strip() + ".", 0.0) for chunk in chunks]

    @staticmethod
    def score(summary: str, competitors: list[str], topics: list[str]) -> int:
        """Keyword overlap between a chunk summary and the research query terms."""
        text = summary.lower()
        return sum(1 for term in competitors + topics if term.lower() in text)

    async def select(
        self,
        content: str,
        competitors: list[str],
        topics: list[str],
        summarization_model: str,
    ) -> str:
        """
        Full pipeline: split → summarize+score → select top_k → rejoin.

        If the content is already short enough (≤ top_k chunks), it is returned
        as-is without any LLM calls. Selected chunks are always returned in their
        original document order so the main analysis prompt reads naturally.
        """
        chunks = self.split(content)

        if len(chunks) <= self.top_k:
            return content

        log.info("chunker.select_start", total_chunks=len(chunks), top_k=self.top_k)

        results = await self.summarize(chunks, summarization_model, competitors, topics)
        scores = [score for _, score in results]

        above = [i for i, sc in enumerate(scores) if sc >= self.min_relevance]

        if not above:
            log.info(
                "chunker.select_no_relevant_chunks",
                threshold=self.min_relevance,
                max_score=max(scores, default=0.0),
            )
            return ""

        # From above-threshold chunks take top_k, then restore document order
        if len(above) <= self.top_k:
            top_indices = above  # already in document order
        else:
            ranked = sorted(above, key=lambda i: scores[i], reverse=True)
            top_indices = sorted(ranked[: self.top_k])

        selected = [chunks[i] for i in top_indices]
        log.info("chunker.select_done", selected=len(selected), of=len(chunks))
        return "\n\n".join(selected)
