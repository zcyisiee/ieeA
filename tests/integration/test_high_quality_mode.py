"""Integration tests for high-quality translation mode."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from ieeA.parser.latex_parser import LaTeXParser, is_placeholder_only
from ieeA.parser.structure import LaTeXDocument
from ieeA.translator.pipeline import TranslationPipeline
from ieeA.rules.examples import load_examples


class TestPlaceholderFiltering:
    """Tests for placeholder-only content detection."""

    def test_pure_placeholder_detected(self):
        """Verify pure placeholders are correctly identified."""
        assert is_placeholder_only("[[MATH_1]]") is True
        assert is_placeholder_only("[[MATHENV_42]]") is True
        assert is_placeholder_only("[[CITE_5]]") is True
        assert is_placeholder_only("[[REF_123]]") is True

    def test_mixed_content_not_filtered(self):
        """Verify mixed content is not filtered."""
        assert is_placeholder_only("See [[MATH_1]] for details") is False
        assert is_placeholder_only("Text with [[REF_1]] mixed") is False
        assert is_placeholder_only("Before [[MATH_1]] after") is False

    def test_whitespace_handling(self):
        """Verify whitespace is handled correctly."""
        assert is_placeholder_only("  [[MATH_1]]  ") is True
        assert is_placeholder_only("\n[[MATHENV_1]]\n") is True


class TestAbstractExtraction:
    """Tests for abstract extraction functionality."""

    def test_extract_simple_abstract(self):
        """Verify abstract can be extracted from simple LaTeX content."""
        parser = LaTeXParser()
        content = r"""
\documentclass{article}
\begin{document}
\begin{abstract}
This is a test abstract.
\end{abstract}
\end{document}
"""
        abstract = parser.extract_abstract(content)
        assert abstract == "This is a test abstract."

    def test_extract_abstract_with_formatting(self):
        """Verify abstract with LaTeX formatting is extracted."""
        parser = LaTeXParser()
        content = r"""
\begin{abstract}
This is a \textbf{bold} abstract with $math$.
\end{abstract}
"""
        abstract = parser.extract_abstract(content)
        assert "bold" in abstract
        assert "$math$" in abstract

    def test_no_abstract_returns_none(self):
        """Verify None is returned when no abstract exists."""
        parser = LaTeXParser()
        content = r"""
\documentclass{article}
\begin{document}
Some content without abstract.
\end{document}
"""
        abstract = parser.extract_abstract(content)
        assert abstract is None

    def test_empty_abstract_returns_none(self):
        """Verify empty abstract returns None."""
        parser = LaTeXParser()
        content = r"""
\begin{abstract}
\end{abstract}
"""
        abstract = parser.extract_abstract(content)
        assert abstract is None


class TestExamplesLoading:
    """Tests for few-shot examples loading."""

    def test_load_builtin_examples(self):
        """Verify built-in examples can be loaded."""
        examples = load_examples()
        assert len(examples) >= 3

    def test_examples_have_required_fields(self):
        """Verify examples have source and target fields."""
        examples = load_examples()
        for ex in examples:
            assert "source" in ex
            assert "target" in ex
            assert ex["source"]  # Not empty
            assert ex["target"]  # Not empty

    def test_invalid_path_fallback(self):
        """Verify invalid path falls back to built-in examples."""
        examples = load_examples("/nonexistent/path.yaml")
        assert len(examples) >= 3


class TestPipelineWithAbstractContext:
    """Tests for pipeline with abstract context integration."""

    @pytest.mark.asyncio
    async def test_pipeline_accepts_abstract_context(self):
        """Verify pipeline accepts abstract_context parameter."""
        mock_provider = MagicMock()
        mock_provider.translate = AsyncMock(return_value="翻译结果")

        pipeline = TranslationPipeline(
            provider=mock_provider,
            abstract_context="This is the paper abstract.",
            few_shot_examples=[{"source": "test", "target": "测试"}],
        )

        assert pipeline.abstract_context == "This is the paper abstract."
        assert len(pipeline.few_shot_examples) == 1

    @pytest.mark.asyncio
    async def test_pipeline_passes_context_to_provider(self):
        """Verify pipeline passes context to provider."""
        mock_provider = MagicMock()
        mock_provider.translate = AsyncMock(return_value="翻译结果")

        pipeline = TranslationPipeline(
            provider=mock_provider,
            abstract_context="Test abstract content.",
        )

        result = await pipeline.translate_chunk(
            chunk="Test content",
            chunk_id="test-1",
            context="Academic Paper",
        )

        assert result.translation == "翻译结果"
        # Verify translate was called
        mock_provider.translate.assert_called_once()


class TestLaTeXDocumentAbstractField:
    """Tests for LaTeXDocument abstract field."""

    def test_document_has_abstract_field(self):
        """Verify LaTeXDocument has abstract field."""
        assert "abstract" in LaTeXDocument.__dataclass_fields__

    def test_document_abstract_default_none(self):
        """Verify abstract defaults to None."""
        doc = LaTeXDocument(preamble="", chunks=[])
        assert doc.abstract is None

    def test_document_accepts_abstract(self):
        """Verify document can store abstract."""
        doc = LaTeXDocument(preamble="", chunks=[], abstract="Test abstract")
        assert doc.abstract == "Test abstract"
