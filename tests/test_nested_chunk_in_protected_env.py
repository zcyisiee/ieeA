"""Tests for nested translatable chunks inside protected environments."""

import pytest
from pathlib import Path
import tempfile
from ieeA.parser.latex_parser import LaTeXParser
from ieeA.parser.structure import LaTeXDocument, Chunk


class TestNestedChunkInProtectedEnv:
    """Test that translatable chunks inside protected environments are correctly handled."""

    def test_caption_in_algorithm_is_translated(self):
        """Test that caption inside algorithm environment is translated.

        This is the core issue: algorithm is a protected environment,
        but caption inside it should still be translatable.

        Processing order:
        1. _extract_captions() creates {{CHUNK_uuid}} for caption
        2. _protect_math_environments() wraps algorithm in [[ENV_n]]
        3. The {{CHUNK_uuid}} is now INSIDE [[ENV_n]]'s value

        Expected behavior after fix:
        - When reconstructing, global_placeholders should be restored FIRST
        - This exposes the {{CHUNK_uuid}} in the document
        - Then chunk replacement can find and translate it
        """
        doc_with_algorithm = r"""
\documentclass{article}
\usepackage{algorithm}
\usepackage{algorithmic}
\begin{document}

\begin{algorithm}
\caption{My Algorithm Description}
\begin{algorithmic}[1]
\STATE Initialize $x = 0$
\STATE Compute $y = x + 1$
\end{algorithmic}
\end{algorithm}

\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(doc_with_algorithm)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Verify caption chunk was created
            caption_chunks = [c for c in doc.chunks if c.context == "caption"]
            assert len(caption_chunks) == 1, (
                f"Should have 1 caption chunk, got {len(caption_chunks)}"
            )
            assert "My Algorithm Description" in caption_chunks[0].content, (
                "Caption chunk should contain the caption text"
            )

            # Verify algorithm environment was protected
            algorithm_placeholders = [
                k for k in doc.global_placeholders.keys() if "ENV" in k
            ]
            assert len(algorithm_placeholders) >= 1, (
                "Algorithm should be protected as ENV"
            )

            # Simulate translation: replace caption content with Chinese
            translated_chunks = {caption_chunks[0].id: "我的算法描述"}

            # Reconstruct with translation
            reconstructed = doc.reconstruct(translated_chunks)

            # THE KEY ASSERTION: translated caption should appear in output
            assert "我的算法描述" in reconstructed, (
                f"Translated caption should appear in reconstructed document. "
                f"Got: {reconstructed[:1000]}"
            )

            # Original English should NOT appear (it was translated)
            assert "My Algorithm Description" not in reconstructed, (
                "Original caption text should be replaced with translation"
            )

            # Algorithm structure should be preserved
            assert r"\begin{algorithm}" in reconstructed
            assert r"\end{algorithm}" in reconstructed
            assert r"\begin{algorithmic}" in reconstructed

        finally:
            Path(temp_path).unlink()

    def test_multiple_captions_in_protected_envs(self):
        """Test multiple captions in different protected environments."""
        doc_content = r"""
\documentclass{article}
\usepackage{algorithm}
\usepackage{algorithmic}
\begin{document}

\begin{algorithm}
\caption{First Algorithm}
\begin{algorithmic}[1]
\STATE Step 1
\end{algorithmic}
\end{algorithm}

Some text between algorithms.

\begin{algorithm}
\caption{Second Algorithm}
\begin{algorithmic}[1]
\STATE Step 2
\end{algorithmic}
\end{algorithm}

\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(doc_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Should have 2 caption chunks
            caption_chunks = [c for c in doc.chunks if c.context == "caption"]
            assert len(caption_chunks) == 2, (
                f"Should have 2 caption chunks, got {len(caption_chunks)}"
            )

            # Translate both
            translated_chunks = {}
            for chunk in caption_chunks:
                if "First" in chunk.content:
                    translated_chunks[chunk.id] = "第一个算法"
                elif "Second" in chunk.content:
                    translated_chunks[chunk.id] = "第二个算法"

            reconstructed = doc.reconstruct(translated_chunks)

            # Both translations should appear
            assert "第一个算法" in reconstructed, "First caption should be translated"
            assert "第二个算法" in reconstructed, "Second caption should be translated"

            # Original text should not appear
            assert "First Algorithm" not in reconstructed
            assert "Second Algorithm" not in reconstructed

        finally:
            Path(temp_path).unlink()

    def test_caption_in_figure_still_works(self):
        """Test that caption in figure (non-protected env) still works.

        This is a regression test - figure is NOT a protected environment,
        so captions there should work before and after the fix.
        """
        doc_content = r"""
\documentclass{article}
\begin{document}

\begin{figure}
\centering
\caption{A beautiful figure}
\end{figure}

\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(doc_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            caption_chunks = [c for c in doc.chunks if c.context == "caption"]
            assert len(caption_chunks) == 1

            translated_chunks = {caption_chunks[0].id: "一个漂亮的图片"}

            reconstructed = doc.reconstruct(translated_chunks)

            assert "一个漂亮的图片" in reconstructed
            assert "A beautiful figure" not in reconstructed

        finally:
            Path(temp_path).unlink()

    def test_nested_math_in_caption_in_algorithm(self):
        """Test caption with math inside algorithm environment.

        This is a complex nesting scenario:
        - Algorithm (protected env) contains
          - Caption (translatable chunk) contains
            - Math (protected placeholder)
        """
        doc_content = r"""
\documentclass{article}
\usepackage{algorithm}
\usepackage{algorithmic}
\begin{document}

\begin{algorithm}
\caption{Computing $f(x) = x^2$ efficiently}
\begin{algorithmic}[1]
\STATE Compute $y = x * x$
\end{algorithmic}
\end{algorithm}

\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(doc_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            caption_chunks = [c for c in doc.chunks if c.context == "caption"]
            assert len(caption_chunks) == 1

            # The caption content should have math placeholder
            caption_content = caption_chunks[0].content
            assert "[[MATH_" in caption_content or "$f(x)" in caption_content, (
                f"Caption should contain math. Got: {caption_content}"
            )

            # Translate the text part, keep math placeholder
            # Note: the translator would preserve [[MATH_n]] placeholders
            translated_content = caption_content.replace("Computing", "计算").replace(
                "efficiently", "高效地"
            )
            translated_chunks = {caption_chunks[0].id: translated_content}

            reconstructed = doc.reconstruct(translated_chunks)

            # Should have translated text
            assert "计算" in reconstructed or "高效地" in reconstructed, (
                "Translation should appear"
            )

            # Should have math restored
            assert "$f(x) = x^2$" in reconstructed or "f(x)" in reconstructed, (
                "Math should be preserved"
            )

        finally:
            Path(temp_path).unlink()
