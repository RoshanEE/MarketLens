"""
Tests for ContentChunker.

Run with:
    cd backend
    pytest tests/test_chunker.py -v

Requires: pytest, pytest-asyncio
    pip install pytest pytest-asyncio
"""

import json
import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.chunker import ContentChunker, _MIN_CHUNK, _CHUNK_SIZE, _TOP_K, _MIN_RELEVANCE


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_chunker(top_k: int = _TOP_K, chunk_size: int = _CHUNK_SIZE) -> ContentChunker:
    """Return a ContentChunker with a mocked LLMClient."""
    llm = MagicMock()
    llm.complete = AsyncMock()
    return ContentChunker(llm=llm, chunk_size=chunk_size, top_k=top_k)


def para(length: int, char: str = "x") -> str:
    """Return a paragraph of exactly `length` characters."""
    return char * length


# ---------------------------------------------------------------------------
# split()
# ---------------------------------------------------------------------------

class TestSplit:
    def test_empty_content_returns_empty_list(self):
        chunker = make_chunker()
        assert chunker.split("") == []

    def test_whitespace_only_returns_empty_list(self):
        chunker = make_chunker()
        assert chunker.split("   \n\n   \n\n   ") == []

    def test_single_short_paragraph_below_min_chunk_is_discarded(self):
        chunker = make_chunker()
        short = para(_MIN_CHUNK - 1)
        assert chunker.split(short) == []

    def test_single_paragraph_at_min_chunk_is_kept(self):
        chunker = make_chunker()
        content = para(_MIN_CHUNK)
        assert chunker.split(content) == [content]

    def test_single_paragraph_above_min_chunk_is_kept(self):
        chunker = make_chunker()
        content = para(_MIN_CHUNK + 50)
        assert chunker.split(content) == [content]

    def test_two_short_paragraphs_are_merged_into_one_chunk(self):
        """Two paragraphs that together fit within chunk_size should be merged."""
        chunker = make_chunker()
        p1 = para(_MIN_CHUNK)
        p2 = para(_MIN_CHUNK)
        # combined length = _MIN_CHUNK*2 + 2 (for "\n\n") which is well under _CHUNK_SIZE=800
        result = chunker.split(f"{p1}\n\n{p2}")
        assert len(result) == 1
        assert p1 in result[0]
        assert p2 in result[0]

    def test_two_large_paragraphs_are_kept_as_separate_chunks(self):
        """Two paragraphs whose combined length exceeds chunk_size stay separate."""
        chunker = make_chunker(chunk_size=400)
        p1 = para(250)
        p2 = para(250)
        result = chunker.split(f"{p1}\n\n{p2}")
        assert result == [p1, p2]

    def test_preserves_paragraph_order(self):
        chunker = make_chunker(chunk_size=300)
        paragraphs = [para(200, char) for char in "abcd"]
        content = "\n\n".join(paragraphs)
        result = chunker.split(content)
        assert result == paragraphs

    def test_short_standalone_paragraph_between_long_ones_is_discarded(self):
        """A paragraph below _MIN_CHUNK that can't merge is dropped."""
        chunker = make_chunker(chunk_size=300)
        p_long1 = para(250)
        p_short = para(_MIN_CHUNK - 1, "s")
        p_long2 = para(250, "y")
        content = f"{p_long1}\n\n{p_short}\n\n{p_long2}"
        result = chunker.split(content)
        # p_long1 fills the chunk, p_short becomes current but then p_long2 can't merge
        # p_short (< _MIN_CHUNK) is discarded, p_long2 is kept
        assert p_long1 in result
        assert p_long2 in result
        assert p_short not in result

    def test_multiple_blank_lines_treated_as_paragraph_separator(self):
        """Three or more blank lines still split paragraphs."""
        chunker = make_chunker()
        p1 = para(_MIN_CHUNK)
        p2 = para(_MIN_CHUNK + 10, "y")
        # Three newlines between paragraphs
        result = chunker.split(f"{p1}\n\n\n{p2}")
        assert len(result) == 1  # they're merged since combined < _CHUNK_SIZE
        assert p1 in result[0] and p2 in result[0]


# ---------------------------------------------------------------------------
# score()
# ---------------------------------------------------------------------------

class TestScore:
    def test_no_terms_returns_zero(self):
        assert ContentChunker.score("any summary text", [], []) == 0

    def test_no_match_returns_zero(self):
        assert ContentChunker.score("some text about nothing", ["apple"], ["banana"]) == 0

    def test_competitor_match_counted(self):
        assert ContentChunker.score("apple launched a new product", ["apple"], []) == 1

    def test_topic_match_counted(self):
        assert ContentChunker.score("market analysis of pricing", [], ["pricing"]) == 1

    def test_multiple_term_matches_summed(self):
        score = ContentChunker.score(
            "apple and google compete on pricing",
            ["apple", "google"],
            ["pricing"],
        )
        assert score == 3

    def test_case_insensitive_matching(self):
        assert ContentChunker.score("Apple Inc. leads the market", ["apple"], []) == 1

    def test_partial_substring_still_matches(self):
        # "pricing" is in "repricing"
        assert ContentChunker.score("repricing strategy", [], ["pricing"]) == 1

    def test_empty_summary_returns_zero(self):
        assert ContentChunker.score("", ["apple"], ["market"]) == 0


# ---------------------------------------------------------------------------
# summarize()
# ---------------------------------------------------------------------------

def _sr(summary: str, relevance: float) -> dict:
    """Shorthand for building a summarize response item."""
    return {"summary": summary, "relevance": relevance}


@pytest.mark.asyncio
class TestSummarize:
    async def test_empty_chunks_returns_empty_list(self):
        chunker = make_chunker()
        result = await chunker.summarize([], model="claude-haiku-4-5-20251001")
        assert result == []
        chunker.llm.complete.assert_not_called()

    async def test_valid_json_response_parsed_correctly(self):
        chunker = make_chunker()
        chunks = ["First chunk content here.", "Second chunk content here."]
        chunker.llm.complete.return_value = json.dumps([
            _sr("Summary one.", 8.0),
            _sr("Summary two.", 3.5),
        ])

        result = await chunker.summarize(chunks, model="claude-haiku-4-5-20251001")
        assert result == [("Summary one.", 8.0), ("Summary two.", 3.5)]

    async def test_relevance_scores_returned_as_floats(self):
        chunker = make_chunker()
        chunks = ["Chunk about pricing strategy.", "Unrelated chunk."]
        chunker.llm.complete.return_value = json.dumps([
            _sr("Pricing strategy discussed.", 9.5),
            _sr("Unrelated content.", 0.0),
        ])

        result = await chunker.summarize(
            chunks, model="claude-haiku-4-5-20251001",
            competitors=["Apple"], topics=["pricing"],
        )
        summaries = [s for s, _ in result]
        scores = [sc for _, sc in result]
        assert summaries == ["Pricing strategy discussed.", "Unrelated content."]
        assert scores == [9.5, 0.0]

    async def test_competitors_and_topics_passed_to_llm_prompt(self):
        """The LLM prompt must include the query terms so it can score relevance."""
        chunker = make_chunker()
        chunks = ["Some chunk."]
        chunker.llm.complete.return_value = json.dumps([_sr("A summary.", 5.0)])

        await chunker.summarize(
            chunks, model="claude-haiku-4-5-20251001",
            competitors=["Apple"], topics=["pricing"],
        )

        call_kwargs = chunker.llm.complete.call_args
        prompt = call_kwargs.kwargs.get("user") or call_kwargs.args[2]
        assert "Apple" in prompt
        assert "pricing" in prompt

    async def test_markdown_code_block_stripped_before_parsing(self):
        chunker = make_chunker()
        chunks = ["Chunk A.", "Chunk B."]
        payload = [_sr("A summary.", 7.0), _sr("B summary.", 2.0)]
        chunker.llm.complete.return_value = f"```json\n{json.dumps(payload)}\n```"

        result = await chunker.summarize(chunks, model="claude-haiku-4-5-20251001")
        assert result == [("A summary.", 7.0), ("B summary.", 2.0)]

    async def test_length_mismatch_falls_back_to_first_sentence_with_zero_score(self):
        """If the LLM returns wrong number of items, fall back to first-sentence + 0.0."""
        chunker = make_chunker()
        chunks = ["First sentence. More text.", "Second sentence. More text."]
        # Only one item instead of two
        chunker.llm.complete.return_value = json.dumps([_sr("Only one.", 5.0)])

        result = await chunker.summarize(chunks, model="claude-haiku-4-5-20251001")
        assert result == [("First sentence.", 0.0), ("Second sentence.", 0.0)]

    async def test_invalid_json_falls_back_to_first_sentence_with_zero_score(self):
        chunker = make_chunker()
        chunks = ["Hello world. Extra text.", "Foo bar. Extra text."]
        chunker.llm.complete.return_value = "not valid json at all"

        result = await chunker.summarize(chunks, model="claude-haiku-4-5-20251001")
        assert result == [("Hello world.", 0.0), ("Foo bar.", 0.0)]

    async def test_single_chunk_returns_single_tuple(self):
        chunker = make_chunker()
        chunks = ["Only one chunk of content."]
        chunker.llm.complete.return_value = json.dumps([_sr("One summary.", 6.0)])

        result = await chunker.summarize(chunks, model="claude-haiku-4-5-20251001")
        assert result == [("One summary.", 6.0)]


# ---------------------------------------------------------------------------
# select()
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
class TestSelect:
    async def test_short_content_returned_as_is_without_llm_call(self):
        """When total chunks <= top_k, skip summarize/score entirely."""
        chunker = make_chunker(top_k=4, chunk_size=200)
        # 2 paragraphs of 200 chars each → 2 chunks, top_k=4, so no LLM needed
        p1 = para(200, "a")
        p2 = para(200, "b")
        content = f"{p1}\n\n{p2}"

        result = await chunker.select(
            content,
            competitors=["alpha"],
            topics=["beta"],
            summarization_model="claude-haiku-4-5-20251001",
        )

        assert result == content
        chunker.llm.complete.assert_not_called()

    async def test_top_k_chunks_selected_by_relevance_score(self):
        """High-scoring chunks are preferred over low-scoring ones."""
        chunker = make_chunker(top_k=2, chunk_size=200)

        relevant1   = "Apple dominates the market share. " * 6
        relevant2   = "Google and Apple compete on pricing. " * 6
        irrelevant1 = "The weather today is sunny and warm. " * 6
        irrelevant2 = "Random unrelated content about cooking. " * 5
        content = "\n\n".join([relevant1, relevant2, irrelevant1, irrelevant2])

        chunker.llm.complete.return_value = json.dumps([
            _sr("Apple dominates market share.", 9.0),
            _sr("Google and Apple compete on pricing.", 8.5),
            _sr("The weather is sunny.", 0.5),
            _sr("Random cooking content.", 0.0),
        ])

        result = await chunker.select(
            content,
            competitors=["apple", "google"],
            topics=["pricing", "market"],
            summarization_model="claude-haiku-4-5-20251001",
        )

        assert "Apple dominates" in result
        assert "Google and Apple" in result
        assert "weather" not in result
        assert "cooking" not in result

    async def test_all_chunks_below_threshold_returns_empty_string(self):
        """When every chunk scores below min_relevance the page is considered off-topic."""
        chunker = make_chunker(top_k=2, chunk_size=200)

        chunks_text = [para(200, char) for char in "abcd"]
        content = "\n\n".join(chunks_text)

        chunker.llm.complete.return_value = json.dumps([
            _sr("Summary one.", 0.0),
            _sr("Summary two.", 0.0),
            _sr("Summary three.", 1.0),  # below default _MIN_RELEVANCE of 2.0
            _sr("Summary four.", 1.5),
        ])

        result = await chunker.select(
            content,
            competitors=["nonexistent"],
            topics=["nothing"],
            summarization_model="claude-haiku-4-5-20251001",
        )

        assert result == ""

    async def test_only_above_threshold_chunks_are_selected(self):
        """Chunks below min_relevance are excluded even if top_k slots remain."""
        chunker = make_chunker(top_k=3, chunk_size=200)

        c0 = para(200, "a")  # will score 8.0 — above threshold
        c1 = para(200, "b")  # will score 0.0 — below threshold
        c2 = para(200, "c")  # will score 7.0 — above threshold
        c3 = para(200, "d")  # will score 1.0 — below threshold
        content = "\n\n".join([c0, c1, c2, c3])

        chunker.llm.complete.return_value = json.dumps([
            _sr("Relevant A.", 8.0),
            _sr("Irrelevant B.", 0.0),
            _sr("Relevant C.", 7.0),
            _sr("Irrelevant D.", 1.0),
        ])

        result = await chunker.select(
            content,
            competitors=["alpha"],
            topics=["beta"],
            summarization_model="claude-haiku-4-5-20251001",
        )

        assert c0 in result
        assert c2 in result
        assert c1 not in result  # scored 0.0, below threshold
        assert c3 not in result  # scored 1.0, below threshold

    async def test_custom_min_relevance_threshold_respected(self):
        """A higher min_relevance threshold filters out more chunks."""
        chunker = make_chunker(top_k=2, chunk_size=200)
        chunker.min_relevance = 6.0  # stricter than default 2.0

        c0 = para(200, "a")  # score 5.0 — would pass default threshold but not 6.0
        c1 = para(200, "b")  # score 8.0 — passes
        c2 = para(200, "c")  # score 3.0 — below 6.0
        c3 = para(200, "d")  # score 7.0 — passes
        content = "\n\n".join([c0, c1, c2, c3])

        chunker.llm.complete.return_value = json.dumps([
            _sr("Summary A.", 5.0),
            _sr("Summary B.", 8.0),
            _sr("Summary C.", 3.0),
            _sr("Summary D.", 7.0),
        ])

        result = await chunker.select(
            content,
            competitors=["alpha"],
            topics=["beta"],
            summarization_model="claude-haiku-4-5-20251001",
        )

        assert c1 in result
        assert c3 in result
        assert c0 not in result
        assert c2 not in result

    async def test_selected_chunks_maintain_original_document_order(self):
        """Chunks selected by score are rejoined in their original order, not score order."""
        chunker = make_chunker(top_k=2, chunk_size=200)

        c0 = "Unrelated filler text about nothing special. " * 5
        c1 = "Apple market share grew significantly last quarter. " * 4
        c2 = "Google pricing strategy update announced. " * 5
        c3 = "More unrelated content with no matching terms. " * 5
        content = "\n\n".join([c0, c1, c2, c3])

        chunker.llm.complete.return_value = json.dumps([
            _sr("Unrelated filler.", 0.0),
            _sr("Apple market share grew.", 8.0),
            _sr("Google pricing strategy update.", 8.0),
            _sr("More unrelated content.", 0.5),
        ])

        result = await chunker.select(
            content,
            competitors=["apple", "google"],
            topics=["pricing", "market"],
            summarization_model="claude-haiku-4-5-20251001",
        )

        pos_c1 = result.find("Apple market")
        pos_c2 = result.find("Google pricing")
        assert pos_c1 != -1 and pos_c2 != -1
        assert pos_c1 < pos_c2
