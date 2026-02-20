"""Tests for parser chunk consistency."""

import re
import pytest
import tempfile
from pathlib import Path
from ieeA.parser.latex_parser import LaTeXParser


class TestParserChunkConsistency:
    """Test parser chunk consistency."""

    def test_all_chunks_have_placeholders(self):
        """Every created chunk must have a corresponding placeholder."""
        parser = LaTeXParser()
        # Use a simple test document
        test_content = r"""
\documentclass{article}
\title{Test Title}
\begin{document}
\section{Introduction}
This is a test paragraph.
\paragraph{Setup}
Another paragraph with content.
\end{document}
"""
        # Write temp file and parse
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            doc = parser.parse_file(temp_path)

            # Extract all placeholder IDs
            chunk_ids_in_preamble = set(
                re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", doc.preamble)
            )
            chunk_ids_in_body = set(
                re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", doc.body_template)
            )
            all_placeholder_ids = chunk_ids_in_preamble | chunk_ids_in_body

            chunk_ids_created = set(c.id for c in doc.chunks)
            protected_chunk_ids = set(
                c.id for c in doc.chunks if c.context == "protected"
            )

            orphan_ids = chunk_ids_created - all_placeholder_ids - protected_chunk_ids
            assert len(orphan_ids) == 0, (
                f"Found {len(orphan_ids)} orphan chunks without placeholders: {orphan_ids}"
            )
        finally:
            Path(temp_path).unlink()

    def test_reconstruct_preserves_content(self):
        """Reconstruct without translation should produce valid LaTeX."""
        parser = LaTeXParser()
        test_content = r"""
\documentclass{article}
\begin{document}
\section{Test}
Content here.
\end{document}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            doc = parser.parse_file(temp_path)
            reconstructed = doc.reconstruct(translated_chunks=None)

            # Check no remaining chunk placeholders
            remaining = re.findall(r"\{\{CHUNK_[a-f0-9-]+\}\}", reconstructed)
            assert len(remaining) == 0, (
                f"Found {len(remaining)} unreplaced placeholders in reconstructed document"
            )

            # Verify basic structure is preserved
            assert r"\documentclass{article}" in reconstructed
            assert r"\begin{document}" in reconstructed
            assert r"\end{document}" in reconstructed
        finally:
            Path(temp_path).unlink()

    def test_paragraph_after_section_is_chunked(self):
        """Paragraph command content should be extracted as chunk."""
        parser = LaTeXParser()
        test_content = r"""
\documentclass{article}
\begin{document}
\paragraph{Setup and Methods}
This is the paragraph body.
\end{document}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            doc = parser.parse_file(temp_path)

            # Check paragraph title was extracted
            paragraph_chunks = [c for c in doc.chunks if c.context == "paragraph"]
            assert len(paragraph_chunks) >= 1, (
                "Paragraph command should create at least one chunk"
            )

            # Verify the paragraph title is in one of the chunks
            paragraph_titles = [c.content for c in paragraph_chunks]
            assert any("Setup and Methods" in title for title in paragraph_titles), (
                f"Paragraph title 'Setup and Methods' should be in chunks. Found: {paragraph_titles}"
            )
        finally:
            Path(temp_path).unlink()

    def test_paragraph_body_on_same_line_is_chunked(self):
        """\paragraph{Title} Body text on same line - body should be translatable chunk."""
        parser = LaTeXParser()
        test_content = r"""
\documentclass{article}
\begin{document}
\paragraph{\textbf{Title}} Body text on same line.
\end{document}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            doc = parser.parse_file(temp_path)

            # Find paragraph context chunks (title)
            paragraph_chunks = [c for c in doc.chunks if c.context == "paragraph"]
            assert len(paragraph_chunks) >= 1, (
                "Paragraph command should create at least one chunk"
            )

            # Check that body text "Body text on same line" is in a translatable chunk
            all_chunk_contents = [c.content for c in doc.chunks]
            body_found = any(
                "Body text on same line" in content for content in all_chunk_contents
            )
            assert body_found, (
                f"Body text 'Body text on same line' should be in a translatable chunk. "
                f"Found chunks: {all_chunk_contents}"
            )
        finally:
            Path(temp_path).unlink()

    def test_paragraph_body_on_next_line_still_works(self):
        """\paragraph{Title}\nBody text - regression test for normal case."""
        parser = LaTeXParser()
        test_content = r"""
\documentclass{article}
\begin{document}
\paragraph{\textbf{Title}}
Body text on next line.
\end{document}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            doc = parser.parse_file(temp_path)

            # Check that body text is still found
            all_chunk_contents = [c.content for c in doc.chunks]
            body_found = any(
                "Body text on next line" in content for content in all_chunk_contents
            )
            assert body_found, (
                f"Body text 'Body text on next line' should be in a translatable chunk. "
                f"Found chunks: {all_chunk_contents}"
            )
        finally:
            Path(temp_path).unlink()

    def test_paragraph_without_body_no_crash(self):
        """\paragraph{Title} alone - no crash, title extracted."""
        parser = LaTeXParser()
        test_content = r"""
\documentclass{article}
\begin{document}
\paragraph{\textbf{Title}}
\end{document}
"""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            doc = parser.parse_file(temp_path)

            # Title should be extracted
            paragraph_chunks = [c for c in doc.chunks if c.context == "paragraph"]
            assert len(paragraph_chunks) >= 1, (
                "Paragraph command should create at least one chunk"
            )

            title_found = any("textbf{Title}" in c.content for c in paragraph_chunks)
            assert title_found, f"Title 'textbf{Title}' should be in paragraph chunks"
        finally:
            Path(temp_path).unlink()
