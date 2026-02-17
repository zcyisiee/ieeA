"""Tests for document-level glossary filtering and system prompt stability."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from ieeA.rules.glossary import Glossary, GlossaryEntry
from ieeA.translator.pipeline import TranslationPipeline


@pytest.fixture
def glossary():
    return Glossary(
        terms={
            "AI": GlossaryEntry(target="人工智能"),
            "Transformer": GlossaryEntry(target="Transformer"),
            "CR": GlossaryEntry(target="CR"),
        }
    )


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.translate = AsyncMock(return_value="翻译结果")
    provider._prebuilt_system_prompt = None
    provider._prebuilt_batch_prompt = None
    return provider


@pytest.fixture
def pipeline(mock_provider, glossary):
    return TranslationPipeline(provider=mock_provider, glossary=glossary)


class TestDocumentLevelGlossary:
    """Test document-level glossary filtering."""

    async def test_doc_level_glossary_computed(self, pipeline, mock_provider):
        """Document-level glossary should be computed from all chunks."""
        chunks = [
            {"chunk_id": "c1", "content": "AI is important"},
            {"chunk_id": "c2", "content": "The Transformer model"},
            {"chunk_id": "c3", "content": "The brain works"},
        ]
        await pipeline.translate_document(chunks)

        # Provider should have _prebuilt_system_prompt set
        assert mock_provider._prebuilt_system_prompt is not None

    async def test_prebuilt_prompt_contains_doc_glossary(self, pipeline, mock_provider):
        """Pre-built prompt should contain terms from the full document."""
        # We need to capture the prompt BEFORE translate_document restores it
        # The prompt is set on provider._prebuilt_system_prompt before translation loop
        captured_prompts = []

        original_translate = mock_provider.translate

        async def capture_translate(*args, **kwargs):
            captured_prompts.append(mock_provider._prebuilt_system_prompt)
            return "翻译结果"

        mock_provider.translate = AsyncMock(side_effect=capture_translate)

        chunks = [
            {"chunk_id": "c1", "content": "AI is important"},
            {"chunk_id": "c2", "content": "The Transformer model"},
        ]
        await pipeline.translate_document(chunks)

        # At least one captured prompt should contain our terms
        assert len(captured_prompts) > 0
        prompt = captured_prompts[0]
        assert prompt is not None
        assert "人工智能" in prompt or "AI" in prompt
        assert "Transformer" in prompt

    async def test_filtered_terms_excluded(self, pipeline, mock_provider):
        """Terms not appearing in document (word-boundary) should be excluded."""
        captured_prompts = []

        async def capture_translate(*args, **kwargs):
            captured_prompts.append(mock_provider._prebuilt_system_prompt)
            return "翻译结果"

        mock_provider.translate = AsyncMock(side_effect=capture_translate)

        chunks = [
            {"chunk_id": "c1", "content": "AI is important"},
            {"chunk_id": "c2", "content": "across the field"},  # 'CR' should NOT match
        ]
        await pipeline.translate_document(chunks)

        assert len(captured_prompts) > 0
        prompt = captured_prompts[0]
        assert prompt is not None
        # CR should not be in glossary section (it may appear in other parts of the prompt)
        if "术语表" in prompt:
            glossary_section = prompt[prompt.index("术语表") :]
            assert "- CR: CR" not in glossary_section


class TestPromptStability:
    """Test that system prompts are stable across chunks."""

    async def test_all_chunks_use_glossary_hints_none(self, pipeline, mock_provider):
        """All individual chunk translations should pass glossary_hints=None."""
        # Use chunks longer than batch threshold (300 chars) to go through individual path
        long_content = "AI is very important in deep learning. " * 10  # >300 chars
        chunks = [
            {"chunk_id": f"c{i}", "content": f"{long_content} Part {i}"}
            for i in range(3)
        ]
        await pipeline.translate_document(chunks)

        # All translate() calls should have glossary_hints=None
        for call in mock_provider.translate.call_args_list:
            kwargs = call.kwargs
            assert kwargs.get("glossary_hints") is None, (
                f"Expected glossary_hints=None, got {kwargs.get('glossary_hints')}"
            )

    async def test_prebuilt_batch_prompt_set(self, pipeline, mock_provider):
        """Batch prompt should be set on the provider."""
        chunks = [
            {"chunk_id": "c1", "content": "AI is important"},  # short, goes to batch
        ]

        # Mock returns batch-formatted response
        mock_provider.translate = AsyncMock(return_value="[1] 人工智能很重要")

        await pipeline.translate_document(chunks)

        # Both prompts should have been set
        # Note: _prebuilt_batch_prompt is set before loop, but may be swapped during batch
        assert mock_provider._prebuilt_system_prompt is not None
        assert mock_provider._prebuilt_batch_prompt is not None

    async def test_batch_prompt_differs_from_individual(self, pipeline, mock_provider):
        """Batch prompt should differ from individual prompt (has batch_instruction)."""
        # Need a mix of short and long chunks
        long_content = "AI is important in deep learning. " * 20  # >300 chars

        call_count = [0]

        async def smart_translate(*args, **kwargs):
            call_count[0] += 1
            text = kwargs.get("text", args[0] if args else "")
            if text.startswith("[1]"):
                return "[1] 人工智能很重要"
            return "翻译结果"

        mock_provider.translate = AsyncMock(side_effect=smart_translate)

        chunks = [
            {"chunk_id": "c1", "content": "AI is important"},  # short, batch
            {"chunk_id": "c2", "content": long_content},  # long, individual
        ]
        await pipeline.translate_document(chunks)

        assert mock_provider._prebuilt_system_prompt is not None
        assert mock_provider._prebuilt_batch_prompt is not None
        assert (
            mock_provider._prebuilt_system_prompt
            != mock_provider._prebuilt_batch_prompt
        )

    async def test_batch_prompt_contains_batch_instruction(
        self, pipeline, mock_provider
    ):
        """Batch prompt should contain the batch instruction."""
        mock_provider.translate = AsyncMock(return_value="[1] 人工智能很重要")

        chunks = [
            {"chunk_id": "c1", "content": "AI is important"},
        ]
        await pipeline.translate_document(chunks)

        batch_prompt = mock_provider._prebuilt_batch_prompt
        assert batch_prompt is not None
        assert "请翻译以下编号内容" in batch_prompt


class TestPerChunkMetadata:
    """Test that per-chunk metadata is still recorded."""

    async def test_metadata_has_glossary_hints(self, pipeline, mock_provider):
        """TranslatedChunk metadata should contain per-chunk glossary hints."""
        long_content = "AI is very important in deep learning. " * 10

        chunks = [
            {"chunk_id": "c1", "content": long_content},
        ]
        results = await pipeline.translate_document(chunks)

        # Check that metadata has glossary_hints
        for result in results:
            assert "glossary_hints" in result.metadata

    async def test_metadata_glossary_hints_per_chunk(self, pipeline, mock_provider):
        """Each chunk should have its own glossary hints in metadata."""
        long_ai = "AI is very important in deep learning research. " * 10
        long_transformer = "The Transformer architecture is revolutionary. " * 10

        chunks = [
            {"chunk_id": "c1", "content": long_ai},
            {"chunk_id": "c2", "content": long_transformer},
        ]
        results = await pipeline.translate_document(chunks)

        # c1 should have AI hint
        assert "AI" in results[0].metadata["glossary_hints"]
        # c2 should have Transformer hint
        assert "Transformer" in results[1].metadata["glossary_hints"]
