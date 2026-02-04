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
