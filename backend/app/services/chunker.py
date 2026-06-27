"""
Content chunker for handling long web pages.

Splits raw extracted text into paragraph-based chunks, generates a one-sentence
local summary per chunk via a cheap LLM call, scores each chunk by keyword overlap
with the research query, and returns the top-K most relevant chunks in their
original document order.

This avoids the hard character-truncation approach and ensures the most relevant
content reaches the main analysis LLM regardless of where it appears in the page.
"""

import json
import re
import structlog

from app.services.llm_client import LLMClient

log = structlog.get_logger(__name__)

_CHUNK_SIZE = 800    # target chars per chunk
_MIN_CHUNK = 150     # discard chunks shorter than this (nav fragments, captions)
_TOP_K = 8           # chunks to keep per URL

_SUMMARIZE_SYSTEM = (
    "You are a document analyst. Summarize each text chunk in exactly one concise sentence."
)
_SUMMARIZE_PROMPT = """\
Summarize each of the following numbered text chunks in one concise sentence each.
Return a JSON array of strings with exactly {n} items, one per chunk, in the same order.

CHUNKS:
{chunks}"""


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
    ) -> None:
        self.llm = llm
        self.chunk_size = chunk_size
        self.top_k = top_k

    def split(self, content: str) -> list[str]:
        """
        Split content on paragraph boundaries, merging short paragraphs
        into the same chunk until chunk_size is reached.
        """
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", content) if p.strip()]

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

    async def summarize(self, chunks: list[str], model: str) -> list[str]:
        """
        Generate one-sentence summaries for all chunks in a single LLM call.
        Falls back to the first sentence of each chunk if the LLM response
        cannot be parsed.
        """
        if not chunks:
            return []

        formatted = "\n\n".join(f"[{i + 1}] {chunk}" for i, chunk in enumerate(chunks))
        raw = await self.llm.complete(
            model=model,
            system=_SUMMARIZE_SYSTEM,
            user=_SUMMARIZE_PROMPT.format(n=len(chunks), chunks=formatted),
            max_tokens=max(256, len(chunks) * 80),
        )
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]

        try:
            summaries = json.loads(raw)
            if isinstance(summaries, list) and len(summaries) == len(chunks):
                return [str(s) for s in summaries]
            log.warning("chunker.summarize_length_mismatch", expected=len(chunks), got=len(summaries))
        except (json.JSONDecodeError, ValueError):
            log.warning("chunker.summarize_parse_error", raw=raw[:300])

        # Fallback: first sentence of each chunk
        return [chunk.split(".")[0].strip() + "." for chunk in chunks]

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
        Full pipeline: split → summarize → score → select top_k → rejoin.

        If the content is already short enough (≤ top_k chunks), it is returned
        as-is without any LLM calls. Selected chunks are always returned in their
        original document order so the main analysis prompt reads naturally.
        """
        chunks = self.split(content)

        if len(chunks) <= self.top_k:
            return content

        log.info("chunker.select_start", total_chunks=len(chunks), top_k=self.top_k)

        summaries = await self.summarize(chunks, summarization_model)
        scores = [self.score(summaries[i], competitors, topics) for i in range(len(chunks))]

        if max(scores, default=0) == 0:
            # No relevance signal — keep the first top_k chunks (document head)
            top_indices = list(range(self.top_k))
        else:
            ranked = sorted(range(len(chunks)), key=lambda i: scores[i], reverse=True)
            top_indices = sorted(ranked[: self.top_k])  # restore original order

        selected = [chunks[i] for i in top_indices]
        log.info("chunker.select_done", selected=len(selected), of=len(chunks))
        return "\n\n".join(selected)
