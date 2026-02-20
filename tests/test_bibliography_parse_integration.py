"""
Integration test for bibliography resolution in parse_file() workflow.

This test verifies that _resolve_bibliography() is called during parse_file()
at the correct position: after _flatten_latex() and before _remove_comments().
"""

import os
import tempfile
import pytest
from pathlib import Path

from ieeA.parser.latex_parser import LaTeXParser


class TestBibliographyInParseFlow:
    """Test bibliography resolution happens during parse_file() workflow."""

    def test_bibliography_resolved_during_parse_with_bbl_only(self):
        """
        When only .bbl files exist (no .bib), bibliography commands should be
        resolved to \input{} commands during parse_file().
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create main.tex with bibliography command
            main_tex = Path(tmpdir) / "main.tex"
            main_tex.write_text(r"""\documentclass{article}
\bibliographystyle{plain}
\begin{document}
Hello world.
\bibliography{references}
\end{document}
""")

            # Create references.bbl (but NOT references.bib)
            bbl_file = Path(tmpdir) / "references.bbl"
            bbl_file.write_text(r"""\begin{thebibliography}{1}
\bibitem{test} Test Author, \textit{Test Title}, 2024.
\end{thebibliography}
""")

            parser = LaTeXParser()
            doc = parser.parse_file(str(main_tex))

            # The body_template should contain \input{references.bbl} instead of \bibliography{references}
            assert r"\bibliography{references}" not in doc.body_template
            assert r"\input{references.bbl}" in doc.body_template
            # \bibliographystyle should be removed
            assert r"\bibliographystyle{plain}" not in doc.preamble

    def test_bibliography_unchanged_when_bib_exists(self):
        """
        When .bib file exists, bibliography commands should remain unchanged.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create main.tex with bibliography command
            main_tex = Path(tmpdir) / "main.tex"
            main_tex.write_text(r"""\documentclass{article}
\bibliographystyle{plain}
\begin{document}
Hello world.
\bibliography{references}
\end{document}
""")

            # Create both .bib and .bbl files
            bib_file = Path(tmpdir) / "references.bib"
            bib_file.write_text("""@article{test,
  author = {Test Author},
  title = {Test Title},
  year = {2024}
}
""")

            bbl_file = Path(tmpdir) / "references.bbl"
            bbl_file.write_text("Some content")

            parser = LaTeXParser()
            doc = parser.parse_file(str(main_tex))

            # Original bibliography command should be preserved
            assert r"\bibliography{references}" in doc.body_template
            # \bibliographystyle should also be preserved
            assert r"\bibliographystyle{plain}" in doc.preamble

    def test_bibliography_resolution_order_in_pipeline(self):
        """
        Verify bibliography resolution happens after flatten and before comment removal.

        This ensures that:
        1. Bibliography commands from included files are also resolved
        2. Trailing comments on bibliography lines are handled correctly
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create main.tex that includes another file with bibliography
            main_tex = Path(tmpdir) / "main.tex"
            main_tex.write_text(r"""\documentclass{article}
\input{chapter}
\begin{document}
Hello world.
\end{document}
""")

            # Create chapter.tex with bibliography command and trailing comment
            chapter_tex = Path(tmpdir) / "chapter.tex"
            chapter_tex.write_text(r"""\bibliographystyle{plain} % style comment
\bibliography{refs} % bibliography comment
""")

            # Create refs.bbl (but NOT refs.bib)
            bbl_file = Path(tmpdir) / "refs.bbl"
            bbl_file.write_text(r"""\begin{thebibliography}{1}
\bibitem{ref1} Author, Title, 2024.
\end{thebibliography}
""")

            parser = LaTeXParser()
            doc = parser.parse_file(str(main_tex))

            # The flattened content should have resolved bibliography
            assert r"\bibliography{refs}" not in (doc.preamble + doc.body_template)
            assert r"\input{refs.bbl}" in (doc.preamble + doc.body_template)
            # Comments should be removed (by _remove_comments which runs after _resolve_bibliography)
            assert "% style comment" not in doc.preamble
            assert "% bibliography comment" not in doc.preamble

    def test_multiple_bibliography_files_all_bbl(self):
        """
        Test with multiple bibliography entries all having only .bbl files.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            main_tex = Path(tmpdir) / "main.tex"
            main_tex.write_text(r"""\documentclass{article}
\bibliographystyle{plain}
\begin{document}
Content here.
\bibliography{refs1,refs2}
\end{document}
""")

            # Create both .bbl files but no .bib files
            (Path(tmpdir) / "refs1.bbl").write_text("Refs1 content")
            (Path(tmpdir) / "refs2.bbl").write_text("Refs2 content")

            parser = LaTeXParser()
            doc = parser.parse_file(str(main_tex))

            # Should be replaced with multiple \input commands
            assert r"\bibliography{refs1,refs2}" not in doc.body_template
            assert r"\input{refs1.bbl}" in doc.body_template
            assert r"\input{refs2.bbl}" in doc.body_template

    def test_multiple_bibliography_files_some_bib(self):
        """
        Test with multiple bibliography entries where some have .bib files.
        When ANY entry has a .bib file, all should be left unchanged.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            main_tex = Path(tmpdir) / "main.tex"
            main_tex.write_text(r"""\documentclass{article}
\bibliographystyle{plain}
\begin{document}
Content here.
\bibliography{refs1,refs2}
\end{document}
""")

            # refs1 has .bib file, refs2 only has .bbl
            (Path(tmpdir) / "refs1.bib").write_text("@article{x, title={X}}")
            (Path(tmpdir) / "refs1.bbl").write_text("Refs1 content")
            (Path(tmpdir) / "refs2.bbl").write_text("Refs2 content")

            parser = LaTeXParser()
            doc = parser.parse_file(str(main_tex))

            # Original should be preserved because refs1 has .bib
            assert r"\bibliography{refs1,refs2}" in doc.body_template
