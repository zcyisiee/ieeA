"""Tests for translation pipeline - TDD RED phase."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import sys

# Mock external dependencies before importing
sys.modules["openai"] = MagicMock()
sys.modules["tiktoken"] = MagicMock()
sys.modules["anthropic"] = MagicMock()
sys.modules["dashscope"] = MagicMock()
sys.modules["volcenginesdkarkruntime"] = MagicMock()

from ieet.rules.glossary import Glossary, GlossaryEntry
from ieet.translator.pipeline import (
    TranslationPipeline,
    TranslatedChunk,
    GlossaryPreprocessor,
)
from ieet.translator.prompts import build_translation_prompt


class TestGlossaryPreprocessor:
    """Test glossary term replacement with placeholders."""

    def test_preprocess_replaces_terms_with_placeholders(self):
        """Glossary terms should be replaced with numbered placeholders."""
        glossary = Glossary.from_dict({
            "attention mechanism": "注意力机制",
            "transformer": "Transformer架构",
        })
        preprocessor = GlossaryPreprocessor(glossary)
        
        text = "The attention mechanism in transformer models is powerful."
        result, mapping = preprocessor.preprocess(text)
        
        # Terms should be replaced with placeholders
        assert "attention mechanism" not in result
        assert "transformer" not in result
        assert "{{GLOSS_" in result
        # Mapping should track the replacements
        assert len(mapping) == 2

    def test_preprocess_case_sensitive(self):
        """Preprocessing should be case-sensitive by default."""
        glossary = Glossary.from_dict({
            "Transformer": "Transformer架构",
        })
        preprocessor = GlossaryPreprocessor(glossary)
        
        text = "The transformer model uses Transformer architecture."
        result, mapping = preprocessor.preprocess(text)
        
        # Only "Transformer" (capitalized) should be replaced
        assert "transformer model" in result  # lowercase kept
        assert "{{GLOSS_" in result  # capitalized replaced
        assert len(mapping) == 1

    def test_postprocess_restores_placeholders(self):
        """Placeholders should be restored with translated terms."""
        glossary = Glossary.from_dict({
            "attention": "注意力",
        })
        preprocessor = GlossaryPreprocessor(glossary)
        
        # Simulate preprocessed text and mapping
        text = "The {{GLOSS_001}} is important."
        mapping = {"{{GLOSS_001}}": "attention"}
        
        result = preprocessor.postprocess(text, mapping)
        
        assert result == "The 注意力 is important."

    def test_preprocess_handles_overlapping_terms(self):
        """Longer terms should be matched first to avoid partial replacements."""
        glossary = Glossary.from_dict({
            "attention": "注意力",
            "attention mechanism": "注意力机制",
        })
        preprocessor = GlossaryPreprocessor(glossary)
        
        text = "The attention mechanism is based on attention."
        result, mapping = preprocessor.preprocess(text)
        
        # "attention mechanism" should be replaced as a whole
        # "attention" at the end should also be replaced separately
        assert len(mapping) == 2

    def test_preprocess_empty_text(self):
        """Empty text should return empty result."""
        glossary = Glossary.from_dict({"term": "术语"})
        preprocessor = GlossaryPreprocessor(glossary)
        
        result, mapping = preprocessor.preprocess("")
        
        assert result == ""
        assert len(mapping) == 0


class TestBuildTranslationPrompt:
    """Test prompt building with templates."""

    def test_build_basic_prompt(self):
        """Basic prompt should include content."""
        prompt = build_translation_prompt(
            content="Hello world",
        )
        
        assert "Hello world" in prompt
        assert "翻译" in prompt or "translate" in prompt.lower()

    def test_build_prompt_with_glossary_hints(self):
        """Prompt should include glossary hints when provided."""
        prompt = build_translation_prompt(
            content="Test content",
            glossary_hints={"attention": "注意力", "model": "模型"},
        )
        
        assert "attention" in prompt
        assert "注意力" in prompt

    def test_build_prompt_with_context(self):
        """Prompt should include context information."""
        prompt = build_translation_prompt(
            content="Test content",
            context="This is from an AI paper about transformers.",
        )
        
        assert "AI paper" in prompt or "transformers" in prompt

    def test_build_prompt_with_few_shot_examples(self):
        """Prompt should include few-shot examples when provided."""
        examples = [
            {"source": "The model works.", "target": "该模型有效。"},
        ]
        prompt = build_translation_prompt(
            content="Test content",
            few_shot_examples=examples,
        )
        
        assert "The model works." in prompt
        assert "该模型有效。" in prompt


class TestTranslatedChunk:
    """Test TranslatedChunk data model."""

    def test_translated_chunk_creation(self):
        """TranslatedChunk should store source, translation, and metadata."""
        chunk = TranslatedChunk(
            source="Hello",
            translation="你好",
            chunk_id="chunk_001",
        )
        
        assert chunk.source == "Hello"
        assert chunk.translation == "你好"
        assert chunk.chunk_id == "chunk_001"

    def test_translated_chunk_with_metadata(self):
        """TranslatedChunk should support optional metadata."""
        chunk = TranslatedChunk(
            source="Hello",
            translation="你好",
            chunk_id="chunk_001",
            metadata={"tokens": 10, "model": "gpt-4"},
        )
        
        assert chunk.metadata["tokens"] == 10
        assert chunk.metadata["model"] == "gpt-4"


class TestTranslationPipeline:
    """Test the main translation pipeline."""

    @pytest.fixture
    def mock_provider(self):
        """Create a mock LLM provider."""
        provider = MagicMock()
        provider.translate = AsyncMock(return_value="翻译后的文本")
        provider.estimate_tokens = MagicMock(return_value=10)
        return provider

    @pytest.fixture
    def glossary(self):
        """Create a test glossary."""
        return Glossary.from_dict({
            "attention": "注意力",
            "transformer": "Transformer架构",
        })

    @pytest.mark.asyncio
    async def test_translate_chunk_basic(self, mock_provider, glossary):
        """translate_chunk should return TranslatedChunk with translation."""
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
        )
        
        result = await pipeline.translate_chunk(
            chunk="The model uses attention.",
            chunk_id="chunk_001",
        )
        
        assert isinstance(result, TranslatedChunk)
        assert result.source == "The model uses attention."
        assert result.chunk_id == "chunk_001"
        mock_provider.translate.assert_called_once()

    @pytest.mark.asyncio
    async def test_translate_chunk_with_glossary_preprocessing(self, mock_provider, glossary):
        """Glossary terms should be preprocessed before LLM call."""
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
        )
        
        # Provider returns text with placeholder
        mock_provider.translate.return_value = "模型使用{{GLOSS_001}}。"
        
        result = await pipeline.translate_chunk(
            chunk="The model uses attention.",
            chunk_id="chunk_001",
        )
        
        # Placeholder should be restored in final output
        assert "{{GLOSS_" not in result.translation
        assert "注意力" in result.translation

    @pytest.mark.asyncio
    async def test_translate_chunk_with_context(self, mock_provider, glossary):
        """Context should be passed to the provider."""
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
        )
        
        await pipeline.translate_chunk(
            chunk="Test content",
            chunk_id="chunk_001",
            context="This is from an AI paper.",
        )
        
        # Verify context was passed
        call_kwargs = mock_provider.translate.call_args
        assert "context" in call_kwargs.kwargs or len(call_kwargs.args) > 1

    @pytest.mark.asyncio
    async def test_translate_document_processes_all_chunks(self, mock_provider, glossary):
        """translate_document should process all chunks."""
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
        )
        
        chunks = [
            {"chunk_id": "001", "content": "First chunk."},
            {"chunk_id": "002", "content": "Second chunk."},
            {"chunk_id": "003", "content": "Third chunk."},
        ]
        
        results = await pipeline.translate_document(chunks)
        
        assert len(results) == 3
        assert all(isinstance(r, TranslatedChunk) for r in results)
        assert mock_provider.translate.call_count == 3

    @pytest.mark.asyncio
    async def test_translate_document_preserves_order(self, mock_provider, glossary):
        """Translated chunks should maintain original order."""
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
        )
        
        chunks = [
            {"chunk_id": "001", "content": "First"},
            {"chunk_id": "002", "content": "Second"},
        ]
        
        # Return different translations for each call
        mock_provider.translate.side_effect = ["第一", "第二"]
        
        results = await pipeline.translate_document(chunks)
        
        assert results[0].chunk_id == "001"
        assert results[1].chunk_id == "002"


class TestRetryLogic:
    """Test retry and rate limiting functionality."""

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.translate = AsyncMock()
        provider.estimate_tokens = MagicMock(return_value=10)
        return provider

    @pytest.fixture
    def glossary(self):
        return Glossary.from_dict({})

    @pytest.mark.asyncio
    async def test_retry_on_failure(self, mock_provider, glossary):
        """Pipeline should retry on transient failures."""
        # Fail twice, then succeed
        mock_provider.translate.side_effect = [
            RuntimeError("API Error"),
            RuntimeError("API Error"),
            "成功翻译",
        ]
        
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
            max_retries=3,
        )
        
        result = await pipeline.translate_chunk(
            chunk="Test",
            chunk_id="001",
        )
        
        assert result.translation == "成功翻译"
        assert mock_provider.translate.call_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises(self, mock_provider, glossary):
        """Pipeline should raise after max retries exhausted."""
        mock_provider.translate.side_effect = RuntimeError("Persistent Error")
        
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
            max_retries=3,
        )
        
        with pytest.raises(RuntimeError):
            await pipeline.translate_chunk(
                chunk="Test",
                chunk_id="001",
            )
        
        assert mock_provider.translate.call_count == 3

    @pytest.mark.asyncio
    async def test_rate_limiting_delay(self, mock_provider, glossary):
        """Pipeline should respect rate limiting between calls."""
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
            rate_limit_delay=0.01,  # 10ms for testing
        )
        
        mock_provider.translate.return_value = "翻译"
        
        chunks = [
            {"chunk_id": "001", "content": "First"},
            {"chunk_id": "002", "content": "Second"},
        ]
        
        import time
        start = time.time()
        await pipeline.translate_document(chunks)
        elapsed = time.time() - start
        
        # Should have at least one delay between chunks
        assert elapsed >= 0.01


class TestIntermediateState:
    """Test intermediate state saving for resume capability."""

    @pytest.fixture
    def mock_provider(self):
        provider = MagicMock()
        provider.translate = AsyncMock(return_value="翻译")
        provider.estimate_tokens = MagicMock(return_value=10)
        return provider

    @pytest.fixture
    def glossary(self):
        return Glossary.from_dict({})

    @pytest.mark.asyncio
    async def test_saves_intermediate_state(self, mock_provider, glossary, tmp_path):
        """Pipeline should save state after each chunk for resume."""
        state_file = tmp_path / "state.json"
        
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
            state_file=state_file,
        )
        
        chunks = [
            {"chunk_id": "001", "content": "First"},
            {"chunk_id": "002", "content": "Second"},
        ]
        
        await pipeline.translate_document(chunks)
        
        # State file should exist with completed chunks
        assert state_file.exists()
        
        import json
        state = json.loads(state_file.read_text())
        assert len(state["completed"]) == 2

    @pytest.mark.asyncio
    async def test_resumes_from_state(self, mock_provider, glossary, tmp_path):
        """Pipeline should resume from saved state."""
        state_file = tmp_path / "state.json"
        
        # Pre-create state with one completed chunk
        import json
        state_file.write_text(json.dumps({
            "completed": ["001"],
            "results": [{"chunk_id": "001", "source": "First", "translation": "第一"}],
        }))
        
        pipeline = TranslationPipeline(
            provider=mock_provider,
            glossary=glossary,
            state_file=state_file,
        )
        
        chunks = [
            {"chunk_id": "001", "content": "First"},
            {"chunk_id": "002", "content": "Second"},
        ]
        
        results = await pipeline.translate_document(chunks)
        
        # Should only translate the second chunk (first was already done)
        assert mock_provider.translate.call_count == 1
        assert len(results) == 2
