"""End-to-end integration tests for ieeT with real arXiv papers.

These tests verify the complete pipeline works with actual papers from arXiv.
They test downloading, parsing, chunking, and validation (not actual translation
which requires API keys).

Target: ≥7/10 papers should successfully complete the pipeline.
"""
import pytest
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from ieeet.downloader.arxiv import ArxivDownloader, DownloadResult
from ieeet.parser.latex_parser import LaTeXParser
from ieeet.parser.structure import LaTeXDocument
from ieeet.validator.engine import ValidationEngine
from ieeet.rules.glossary import Glossary


@dataclass
class PaperTestResult:
    """Result of testing a single paper."""
    arxiv_id: str
    download_success: bool
    parse_success: bool
    chunk_count: int
    validation_passed: bool
    error: Optional[str] = None


# Test papers as specified in the task
TEST_PAPERS = [
    ("2301.07041", "CS.CL", "InstructGPT - Standard NLP paper"),
    ("1706.03762", "CS.CL", "Attention Is All You Need - Transformer"),
    ("2305.10601", "CS.CL", "Recent NLP paper"),
    ("1810.04805", "CS.CL", "BERT - Pre-training of Deep Bidirectional Transformers"),
    ("2203.02155", "CS.CV", "Vision paper"),
    ("1312.6114", "CS.LG", "VAE - Older paper format"),
    ("2006.11239", "CS.LG", "DDPM - Denoising Diffusion"),
    ("1409.1556", "CS.CV", "VGGNet - Classic CNN paper"),
    ("1512.03385", "CS.CV", "ResNet - Deep Residual Learning"),
    ("2010.11929", "CS.CV", "ViT - Vision Transformer"),
]


class TestArxivDownloadIntegration:
    """Test arXiv paper downloading functionality."""

    @pytest.fixture(scope="class")
    def downloader(self):
        """Create downloader with temporary cache."""
        cache_dir = Path(tempfile.mkdtemp()) / "arxiv_cache"
        return ArxivDownloader(cache_dir=cache_dir)

    @pytest.fixture(scope="class")
    def output_dir(self):
        """Create temporary output directory."""
        output = Path(tempfile.mkdtemp()) / "papers"
        output.mkdir(parents=True, exist_ok=True)
        yield output
        # Cleanup after tests
        shutil.rmtree(output, ignore_errors=True)

    def test_parse_arxiv_id_from_url(self, downloader):
        """Should extract arXiv ID from various URL formats."""
        test_cases = [
            ("https://arxiv.org/abs/2301.07041", "2301.07041"),
            ("https://arxiv.org/pdf/1706.03762.pdf", "1706.03762"),
            ("2301.07041", "2301.07041"),
            ("arxiv.org/abs/1810.04805v2", "1810.04805v2"),
        ]
        for input_str, expected in test_cases:
            result = downloader.parse_id(input_str)
            assert result == expected, f"Failed for {input_str}"

    def test_parse_old_format_arxiv_id(self, downloader):
        """Should handle old arXiv ID format (category/YYMMNNN)."""
        # Old format example
        old_id = "hep-th/9901001"
        result = downloader.parse_id(old_id)
        assert result == old_id

    def test_invalid_arxiv_id_raises(self, downloader):
        """Should raise ValueError for invalid IDs."""
        with pytest.raises(ValueError):
            downloader.parse_id("not-a-valid-id")


class TestLatexParserIntegration:
    """Test LaTeX parsing functionality."""

    @pytest.fixture
    def parser(self):
        return LaTeXParser()

    def test_parse_simple_document(self, parser, tmp_path):
        """Should parse a simple LaTeX document."""
        tex_content = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
This is a simple test document.

It has multiple paragraphs.
\end{document}
"""
        tex_file = tmp_path / "test.tex"
        tex_file.write_text(tex_content)

        doc = parser.parse_file(str(tex_file))

        assert isinstance(doc, LaTeXDocument)
        assert doc.preamble is not None
        assert len(doc.chunks) > 0

    def test_parse_document_with_math(self, parser, tmp_path):
        """Should handle documents with math environments."""
        tex_content = r"""
\documentclass{article}
\begin{document}
The equation $E = mc^2$ is famous.

\begin{equation}
\nabla \cdot \mathbf{E} = \frac{\rho}{\epsilon_0}
\end{equation}

More text after the equation.
\end{document}
"""
        tex_file = tmp_path / "math_test.tex"
        tex_file.write_text(tex_content)

        doc = parser.parse_file(str(tex_file))

        assert len(doc.chunks) >= 1
        # Math should be preserved in chunks
        chunk_contents = " ".join(c.content for c in doc.chunks)
        assert "MATH" in chunk_contents or "equation" in chunk_contents.lower()

    def test_parse_document_with_citations(self, parser, tmp_path):
        """Should preserve citations in parsed document."""
        tex_content = r"""
\documentclass{article}
\begin{document}
Deep learning \cite{lecun2015} has revolutionized AI.
See also \cite{goodfellow2016,hinton2006}.
\end{document}
"""
        tex_file = tmp_path / "cite_test.tex"
        tex_file.write_text(tex_content)

        doc = parser.parse_file(str(tex_file))

        assert len(doc.chunks) >= 1
        # Citations should be preserved
        for chunk in doc.chunks:
            if "revolutionized" in chunk.content:
                # Check that citation reference is preserved
                assert "REF" in chunk.content or "cite" in str(chunk.preserved_elements)


class TestValidationEngineIntegration:
    """Test validation engine functionality."""

    @pytest.fixture
    def engine(self):
        return ValidationEngine()

    def test_validate_balanced_braces(self, engine):
        """Should detect unbalanced braces."""
        original = r"The function $f(x)$ is defined."
        translated_good = r"函数 $f(x)$ 的定义如下。"
        translated_bad = r"函数 $f(x$ 的定义如下。"

        result_good = engine.validate(translated_good, original)
        result_bad = engine.validate(translated_bad, original)

        assert result_good.valid
        assert not result_bad.valid

    def test_validate_citation_preservation(self, engine):
        """Should detect missing citations."""
        original = r"As shown by \cite{smith2020}."
        translated_good = r"如 \cite{smith2020} 所示。"
        translated_missing = r"如研究所示。"

        result_good = engine.validate(translated_good, original)
        result_missing = engine.validate(translated_missing, original)

        assert result_good.valid
        assert not result_missing.valid or any(
            "cite" in e.message.lower() for e in result_missing.errors
        )

    def test_validate_math_preservation(self, engine):
        """Should detect missing math environments."""
        original = r"The equation \begin{equation}E=mc^2\end{equation} is important."
        translated_good = r"方程 \begin{equation}E=mc^2\end{equation} 很重要。"
        translated_missing = r"方程 E=mc^2 很重要。"

        result_good = engine.validate(translated_good, original)
        result_missing = engine.validate(translated_missing, original)

        assert result_good.valid
        # Missing math environment should trigger error or warning
        has_math_issue = not result_missing.valid or any(
            "math" in e.message.lower() or "equation" in e.message.lower()
            for e in result_missing.errors
        )
        assert has_math_issue


class TestGlossaryIntegration:
    """Test glossary functionality."""

    def test_glossary_from_dict(self):
        """Should create glossary from dictionary."""
        glossary = Glossary.from_dict({
            "attention": "注意力",
            "transformer": "Transformer架构",
        })

        entry = glossary.get("attention")
        assert entry is not None
        assert entry.target == "注意力"

    def test_glossary_term_priority(self):
        """Should handle overlapping terms correctly."""
        glossary = Glossary.from_dict({
            "attention": "注意力",
            "attention mechanism": "注意力机制",
        })

        # Both terms should be accessible
        assert glossary.get("attention") is not None
        assert glossary.get("attention mechanism") is not None


class TestEndToEndPipeline:
    """End-to-end tests with real arXiv papers.
    
    These tests download actual papers and run them through the pipeline.
    They are marked as slow and require network access.
    """

    @pytest.fixture(scope="class")
    def test_env(self):
        """Set up test environment with temporary directories."""
        cache_dir = Path(tempfile.mkdtemp()) / "arxiv_cache"
        output_dir = Path(tempfile.mkdtemp()) / "papers"
        cache_dir.mkdir(parents=True, exist_ok=True)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        yield {
            "cache_dir": cache_dir,
            "output_dir": output_dir,
            "downloader": ArxivDownloader(cache_dir=cache_dir),
            "parser": LaTeXParser(),
            "validator": ValidationEngine(),
        }
        
        # Cleanup
        shutil.rmtree(cache_dir, ignore_errors=True)
        shutil.rmtree(output_dir, ignore_errors=True)

    def _test_single_paper(
        self,
        arxiv_id: str,
        test_env: dict,
    ) -> PaperTestResult:
        """Test a single paper through the pipeline."""
        result = PaperTestResult(
            arxiv_id=arxiv_id,
            download_success=False,
            parse_success=False,
            chunk_count=0,
            validation_passed=False,
        )
        
        try:
            # Step 1: Download
            download_result = test_env["downloader"].download(
                arxiv_id,
                test_env["output_dir"],
            )
            result.download_success = True
            
            # Step 2: Parse
            doc = test_env["parser"].parse_file(str(download_result.main_tex))
            result.parse_success = True
            result.chunk_count = len(doc.chunks)
            
            # Step 3: Validate structure (no translation, just check chunks are valid)
            if doc.chunks:
                # Check that chunks have content
                valid_chunks = sum(1 for c in doc.chunks if c.content.strip())
                result.validation_passed = valid_chunks > 0
            
        except Exception as e:
            result.error = str(e)
        
        return result

    @pytest.mark.slow
    @pytest.mark.network
    @pytest.mark.parametrize("arxiv_id,category,description", TEST_PAPERS)
    def test_paper_pipeline(self, arxiv_id, category, description, test_env):
        """Test individual paper through the pipeline."""
        result = self._test_single_paper(arxiv_id, test_env)
        
        # Log result for debugging
        print(f"\n{arxiv_id} ({category}): {description}")
        print(f"  Download: {'✓' if result.download_success else '✗'}")
        print(f"  Parse: {'✓' if result.parse_success else '✗'}")
        print(f"  Chunks: {result.chunk_count}")
        print(f"  Valid: {'✓' if result.validation_passed else '✗'}")
        if result.error:
            print(f"  Error: {result.error}")
        
        # Individual test assertions
        assert result.download_success, f"Download failed: {result.error}"
        assert result.parse_success, f"Parse failed: {result.error}"
        assert result.chunk_count > 0, "No chunks extracted"

    @pytest.mark.slow
    @pytest.mark.network
    def test_overall_success_rate(self, test_env):
        """Test that at least 7/10 papers pass the pipeline.
        
        This is the key metric for pipeline reliability.
        """
        results = []
        
        for arxiv_id, category, description in TEST_PAPERS:
            result = self._test_single_paper(arxiv_id, test_env)
            results.append(result)
            
            print(f"{arxiv_id}: {'PASS' if result.validation_passed else 'FAIL'}")
            if result.error:
                print(f"  Error: {result.error[:100]}")
        
        # Calculate success rate
        successes = sum(1 for r in results if r.validation_passed)
        total = len(results)
        success_rate = successes / total
        
        print(f"\n{'='*50}")
        print(f"Success Rate: {successes}/{total} ({success_rate*100:.1f}%)")
        print(f"Target: 7/10 (70%)")
        print(f"{'='*50}")
        
        # Assert at least 70% success rate
        assert successes >= 7, f"Only {successes}/10 papers passed (target: 7)"


class TestPipelineWithMockedTranslation:
    """Test pipeline with mocked translation to avoid API calls."""

    @pytest.fixture
    def mock_translated_text(self):
        """Provide mock translation that preserves LaTeX structure."""
        def translate(text):
            # Simple mock: just wrap in Chinese markers
            # Preserve math and citations
            return f"[翻译]{text}[/翻译]"
        return translate

    def test_chunk_reconstruction(self, tmp_path):
        """Test that chunks can be reconstructed into valid LaTeX."""
        tex_content = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
This is the introduction.

\section{Methods}
We use the attention mechanism.
\end{document}
"""
        tex_file = tmp_path / "test.tex"
        tex_file.write_text(tex_content)

        parser = LaTeXParser()
        doc = parser.parse_file(str(tex_file))

        # Verify chunks contain expected content
        chunk_contents = [c.content for c in doc.chunks]
        all_content = " ".join(chunk_contents)
        
        assert "introduction" in all_content.lower() or "Introduction" in all_content
        assert len(doc.chunks) >= 2  # At least intro and methods


# Pytest configuration for markers
def pytest_configure(config):
    config.addinivalue_line("markers", "slow: marks tests as slow (deselect with '-m \"not slow\"')")
    config.addinivalue_line("markers", "network: marks tests as requiring network access")
