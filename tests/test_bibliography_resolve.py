"""Tests for bibliography resolution in LaTeX parser.

Tests _resolve_bibliography() method behavior:
- Only .bbl exists: replace \bibliography{} with \input{}
- .bib exists: keep original command
- Multiple names (comma-separated): handle all
- Mixed case (some .bib, some not): keep original
- Neither file exists: graceful fallback (keep original)
"""

import os
import tempfile
import pytest
from pathlib import Path
from ieeA.parser.latex_parser import LaTeXParser


class TestBibliographyResolve:
    """Test bibliography resolution functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.parser = LaTeXParser()
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_file(self, filename: str, content: str = "") -> str:
        """Helper to create a file in temp directory."""
        filepath = os.path.join(self.temp_dir, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        return filepath

    # ===================================================================
    # RED Phase: Tests for failing scenarios (method doesn't exist yet)
    # ===================================================================

    def test_only_bbl_exists_replaces_bibliography(self):
        """When only .bbl exists, replace \bibliography{} with \input{name.bbl}."""
        # Setup: Create only .bbl file
        self._create_file(
            "refs.bbl",
            "\\begin{thebibliography}\n\\bibitem{test}\n\\end{thebibliography}",
        )

        # Input text with bibliography command
        text = r"\bibliography{refs}"

        # Expected: replaced with \input
        result = self.parser._resolve_bibliography(text, self.temp_dir)

        assert r"\input{refs.bbl}" in result
        assert r"\bibliography{refs}" not in result

    def test_only_bbl_exists_removes_bibliographystyle(self):
        """When replacing bibliography, also remove \bibliographystyle{} line."""
        self._create_file(
            "refs.bbl",
            "\\begin{thebibliography}\n\\bibitem{test}\n\\end{thebibliography}",
        )

        text = r"""\bibliographystyle{plain}
\bibliography{refs}"""

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        assert r"\bibliographystyle{plain}" not in result
        assert r"\input{refs.bbl}" in result

    def test_bib_exists_keeps_original(self):
        """When .bib exists, keep the original \bibliography{} command."""
        # Setup: Create .bib file
        self._create_file("refs.bib", "@article{test, title={Test}}")

        text = r"\bibliography{refs}"

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        # Should keep original
        assert r"\bibliography{refs}" in result
        assert r"\input{refs.bbl}" not in result

    def test_bib_exists_keeps_bibliographystyle(self):
        """When .bib exists, also keep \bibliographystyle{} line."""
        self._create_file("refs.bib", "@article{test, title={Test}}")

        text = r"""\bibliographystyle{plain}
\bibliography{refs}"""

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        assert r"\bibliographystyle{plain}" in result
        assert r"\bibliography{refs}" in result

    def test_multiple_names_all_bbl_replace(self):
        """Multiple bibliography names: if ALL have only .bbl, replace all."""
        self._create_file("refs.bbl", "\\begin{thebibliography}")
        self._create_file("appendix.bbl", "\\begin{thebibliography}")

        text = r"\bibliography{refs,appendix}"

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        # Should replace both with input commands
        assert r"\input{refs.bbl}" in result
        assert r"\input{appendix.bbl}" in result
        assert r"\bibliography{refs,appendix}" not in result

    def test_multiple_names_some_bib_keep_original(self):
        """Multiple bibliography names: if ANY has .bib, keep original command."""
        self._create_file("refs.bib", "@article{test}")
        self._create_file("appendix.bbl", "\\begin{thebibliography}")

        text = r"\bibliography{refs,appendix}"

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        # Should keep original because refs.bib exists
        assert r"\bibliography{refs,appendix}" in result
        assert r"\input{" not in result

    def test_neither_file_exists_keep_original(self):
        """When neither .bib nor .bbl exists, keep original command."""
        text = r"\bibliography{nonexistent}"

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        # Should keep original
        assert r"\bibliography{nonexistent}" in result

    def test_both_files_exist_prefer_bib(self):
        """When both .bib and .bbl exist, prefer .bib (keep original)."""
        self._create_file("refs.bib", "@article{test}")
        self._create_file("refs.bbl", "\\begin{thebibliography}")

        text = r"\bibliography{refs}"

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        # Should keep original because .bib exists
        assert r"\bibliography{refs}" in result

    def test_multiple_bibliography_commands(self):
        """Handle multiple bibliography commands in same text."""
        self._create_file("refs.bbl", "\\begin{thebibliography}")
        self._create_file("other.bib", "@article{other}")

        text = r"""\bibliography{refs}
Some text
\bibliography{other}"""

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        # First should be replaced (only .bbl exists)
        assert r"\input{refs.bbl}" in result
        # Second should be kept (.bib exists)
        assert r"\bibliography{other}" in result

    def test_bibliography_with_spaces_in_names(self):
        """Handle bibliography names with spaces after commas."""
        self._create_file("refs.bbl", "\\begin{thebibliography}")
        self._create_file("appendix.bbl", "\\begin{thebibliography}")

        text = r"\bibliography{refs, appendix}"  # Space after comma

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        # Should handle both names (with space trimmed)
        assert r"\input{refs.bbl}" in result
        assert r"\input{appendix.bbl}" in result

    def test_no_bibliography_command(self):
        """Text without bibliography command should remain unchanged."""
        text = r"\section{Introduction}\nThis is a test."

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        assert result == text

    def test_bibliographystyle_without_bibliography(self):
        """\bibliographystyle without \bibliography should remain."""
        self._create_file("refs.bbl", "\\begin{thebibliography}")

        text = r"\bibliographystyle{plain}"

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        # Should keep as is (no bibliography to trigger replacement)
        assert r"\bibliographystyle{plain}" in result

    def test_preserves_other_commands(self):
        """Ensure other LaTeX commands are preserved."""
        self._create_file("refs.bbl", "\\begin{thebibliography}")

        text = r"""\section{References}
\label{sec:refs}
\bibliographystyle{plain}
\bibliography{refs}
\section{Next}"""

        result = self.parser._resolve_bibliography(text, self.temp_dir)

        assert r"\section{References}" in result
        assert r"\label{sec:refs}" in result
        assert r"\section{Next}" in result
        assert r"\input{refs.bbl}" in result
        assert r"\bibliographystyle{plain}" not in result
