"""Integration tests for escape and bibliography fixes.

End-to-end tests verifying:
1. E2E escape: Parse → Translate (mock) → Reconstruct flow, verify `%` is escaped
2. E2E bibliography: Parse file with .bbl only, verify bibliography is replaced
3. Combined: Both fixes work together
4. Placeholder integrity: Ensure placeholders survive full pipeline
5. Real-world scenario: Test with complex LaTeX structure

These tests verify that the escape_latex_special_chars() and _resolve_bibliography()
functions work correctly through the full pipeline.

NOTE: The LaTeX parser removes comments (lines/content after unescaped %) during parsing,
so we test escaping by introducing special characters in TRANSLATED text (simulating
LLM output), not in the original LaTeX source.
"""

import os
import re
import tempfile
from pathlib import Path
import pytest

from ieeA.parser.latex_parser import LaTeXParser
from ieeA.parser.structure import LaTeXDocument, Chunk, escape_latex_special_chars


class TestE2EEscape:
    """Test end-to-end escaping of special characters through the pipeline."""

    def test_e2e_percent_escape_basic(self):
        """E2E: Basic percent sign escaping through parse → translate → reconstruct."""
        # Original content should use \% since % is a LaTeX comment character
        test_content = r"""\documentclass{article}
\begin{document}
\section{Introduction}
This section covers the theory of algorithms.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            # Step 1: Parse
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Step 2: Mock translate (simulate LLM returning text with %)
            translated_chunks = {}
            for chunk in doc.chunks:
                # Simulate translation that introduces unescaped %
                if "theory of algorithms" in chunk.content:
                    translated_chunks[chunk.id] = (
                        "本节涵盖50%的理论内容"  # Chinese with %
                    )
                else:
                    translated_chunks[chunk.id] = chunk.content

            # Step 3: Reconstruct
            reconstructed = doc.reconstruct(translated_chunks)

            # Step 4: Verify % is escaped
            assert r"50\%" in reconstructed, (
                f"Percent sign should be escaped as '\\%' in reconstructed output.\n"
                f"Reconstructed: {reconstructed[:500]}"
            )
        finally:
            Path(temp_path).unlink()

    def test_e2e_ampersand_escape(self):
        """E2E: Ampersand escaping through full pipeline."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Results}
Smith and Jones showed significant improvement.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Mock translate - introduce & in translation
            translated_chunks = {}
            for chunk in doc.chunks:
                if "Smith and Jones" in chunk.content:
                    translated_chunks[chunk.id] = "史密斯 & 琼斯展示了显著改进"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify & is escaped
            assert r"\&" in reconstructed, (
                f"Ampersand should be escaped as '\\&' in output.\n"
                f"Reconstructed: {reconstructed[:500]}"
            )
        finally:
            Path(temp_path).unlink()

    def test_e2e_hash_escape(self):
        """E2E: Hash sign escaping through full pipeline."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Discussion}
The priority is performance.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Mock translate - introduce # in translation
            translated_chunks = {}
            for chunk in doc.chunks:
                if "priority" in chunk.content:
                    translated_chunks[chunk.id] = "#1 优先级是性能"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify # is escaped
            assert r"\#" in reconstructed, (
                f"Hash should be escaped as '\\#' in output.\n"
                f"Reconstructed: {reconstructed[:500]}"
            )
        finally:
            Path(temp_path).unlink()

    def test_e2e_all_special_chars_together(self):
        """E2E: All special chars (%, &, #) escaped together."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Analysis}
Analysis of performance metrics and rankings.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Mock translate with all special chars
            translated_chunks = {}
            for chunk in doc.chunks:
                if "performance" in chunk.content:
                    translated_chunks[chunk.id] = "A增长5% & B排名第#1，C和D占10%"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify all are escaped
            assert r"5\%" in reconstructed, "Percent should be escaped"
            assert r"\&" in reconstructed, "Ampersand should be escaped"
            assert r"\#" in reconstructed, "Hash should be escaped"
            assert r"10\%" in reconstructed, "Second percent should be escaped"
        finally:
            Path(temp_path).unlink()

    def test_e2e_no_escape_when_no_translation(self):
        """E2E: Original content should NOT be escaped when no translation provided."""
        # Original content uses \% since % is a comment character
        test_content = r"""\documentclass{article}
\begin{document}
\section{Introduction}
Original has 50\% and 100\# items.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Reconstruct without translation (None)
            reconstructed = doc.reconstruct(None)

            # Original content should NOT be double-escaped
            assert r"50\%" in reconstructed, (
                "Original escaped percent should stay as-is"
            )
            assert r"100\#" in reconstructed, "Original escaped hash should stay as-is"
            assert r"50\\%" not in reconstructed, "Should not double-escape"
        finally:
            Path(temp_path).unlink()

    def test_e2e_placeholders_not_escaped(self):
        """E2E: Placeholders in translated text should not be escaped."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Math}
The equation $E=mc^2$ shows efficiency metrics.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Find the chunk that contains the math reference
            translated_chunks = {}
            for chunk in doc.chunks:
                if "efficiency" in chunk.content:
                    # Simulate translation that includes placeholder and special char
                    translated_chunks[chunk.id] = "方程 [[MATH_1]] 展示了 50% 的效率"

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify placeholder is restored, % is escaped
            assert r"$E=mc^2$" in reconstructed, "Math placeholder should be restored"
            assert r"50\%" in reconstructed, "Percent should be escaped"
            assert "[[MATH_" not in reconstructed, "Placeholder markers should be gone"
        finally:
            Path(temp_path).unlink()


class TestE2EBibliography:
    """Test end-to-end bibliography resolution through the pipeline."""

    def test_e2e_bibliography_bbl_only(self):
        """E2E: .bbl only → \bibliography replaced with \input{.bbl}."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .tex file
            tex_content = r"""\documentclass{article}
\begin{document}
\section{Introduction}
See \cite{test2020} for details.

\bibliographystyle{plain}
\bibliography{refs}
\end{document}"""

            tex_path = Path(tmpdir) / "main.tex"
            tex_path.write_text(tex_content, encoding="utf-8")

            # Create .bbl file (but NOT .bib)
            bbl_content = r"""\begin{thebibliography}{1}
\bibitem{test2020} Test Author. Test Title. 2020.
\end{thebibliography}"""

            bbl_path = Path(tmpdir) / "refs.bbl"
            bbl_path.write_text(bbl_content, encoding="utf-8")

            # Parse
            parser = LaTeXParser()
            doc = parser.parse_file(str(tex_path))

            # Reconstruct
            reconstructed = doc.reconstruct()

            # Verify bibliography was replaced
            assert r"\input{refs.bbl}" in reconstructed, (
                f"\bibliography should be replaced with \\input{{refs.bbl}}.\n"
                f"Reconstructed: {reconstructed}"
            )
            assert r"\bibliography{refs}" not in reconstructed, (
                "Original \\bibliography command should be removed"
            )
            assert r"\bibliographystyle{plain}" not in reconstructed, (
                "\\bibliographystyle should be removed when using .bbl"
            )

    def test_e2e_bibliography_bib_exists_keep_original(self):
        """E2E: .bib exists → keep original \bibliography command."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create .tex file
            tex_content = r"""\documentclass{article}
\begin{document}
\section{Introduction}
See \cite{test2020}.

\bibliographystyle{plain}
\bibliography{refs}
\end{document}"""

            tex_path = Path(tmpdir) / "main.tex"
            tex_path.write_text(tex_content, encoding="utf-8")

            # Create BOTH .bib and .bbl files
            bib_content = "@article{test2020, title={Test}}"
            bib_path = Path(tmpdir) / "refs.bib"
            bib_path.write_text(bib_content, encoding="utf-8")

            bbl_path = Path(tmpdir) / "refs.bbl"
            bbl_path.write_text("bbl content", encoding="utf-8")

            # Parse
            parser = LaTeXParser()
            doc = parser.parse_file(str(tex_path))

            # Reconstruct
            reconstructed = doc.reconstruct()

            # Verify original is kept
            assert r"\bibliography{refs}" in reconstructed, (
                f"Original \\bibliography should be kept when .bib exists.\n"
                f"Reconstructed: {reconstructed}"
            )
            assert r"\input{refs.bbl}" not in reconstructed, (
                "Should NOT replace with \\input when .bib exists"
            )
            assert r"\bibliographystyle{plain}" in reconstructed, (
                "\\bibliographystyle should be kept when .bib exists"
            )

    def test_e2e_bibliography_multiple_bbl_files(self):
        """E2E: Multiple .bbl files → all replaced with \input."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_content = r"""\documentclass{article}
\begin{document}
\bibliography{refs,appendix}
\end{document}"""

            tex_path = Path(tmpdir) / "main.tex"
            tex_path.write_text(tex_content, encoding="utf-8")

            # Create both .bbl files
            (Path(tmpdir) / "refs.bbl").write_text("refs bbl", encoding="utf-8")
            (Path(tmpdir) / "appendix.bbl").write_text("appendix bbl", encoding="utf-8")

            parser = LaTeXParser()
            doc = parser.parse_file(str(tex_path))
            reconstructed = doc.reconstruct()

            assert r"\input{refs.bbl}" in reconstructed, "refs.bbl should be input"
            assert r"\input{appendix.bbl}" in reconstructed, (
                "appendix.bbl should be input"
            )
            assert r"\bibliography{refs,appendix}" not in reconstructed, (
                "Original bibliography command should be gone"
            )


class TestCombinedFixes:
    """Test that both escape and bibliography fixes work together."""

    def test_combined_escape_and_bibliography(self):
        """Both fixes: escaped chars in text + bibliography replacement."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_content = r"""\documentclass{article}
\begin{document}
\section{Results}
We achieved improvement and ranked high in tests.
See \cite{key2020} for more.

\bibliographystyle{plain}
\bibliography{refs}
\end{document}"""

            tex_path = Path(tmpdir) / "main.tex"
            tex_path.write_text(tex_content, encoding="utf-8")

            # Create .bbl only (no .bib)
            (Path(tmpdir) / "refs.bbl").write_text(
                r"\begin{thebibliography}{1}\bibitem{key2020}Ref\end{thebibliography}",
                encoding="utf-8",
            )

            parser = LaTeXParser()
            doc = parser.parse_file(str(tex_path))

            # Mock translate with special chars
            translated_chunks = {}
            for chunk in doc.chunks:
                if "improvement" in chunk.content:
                    translated_chunks[chunk.id] = "我们取得了50%的改进，排名第#1"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify both fixes worked
            assert r"50\%" in reconstructed, "Percent should be escaped"
            assert r"\#" in reconstructed, "Hash should be escaped"
            assert r"\input{refs.bbl}" in reconstructed, (
                "Bibliography should be replaced"
            )
            assert r"\bibliography{refs}" not in reconstructed, (
                "Original bibliography should be gone"
            )

    def test_combined_with_citations_and_math(self):
        """Complex: citations, math, special chars, and bibliography."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_content = r"""\documentclass{article}
\usepackage{amsmath}
\begin{document}
\section{Theory}
Equation $E=mc^2$ gives efficiency metrics.
As shown in \cite{einstein1905}, see also \ref{eq:main}.

\begin{equation}\label{eq:main}
x^2 + y^2 = z^2
\end{equation}

\bibliography{physics}
\end{document}"""

            tex_path = Path(tmpdir) / "main.tex"
            tex_path.write_text(tex_content, encoding="utf-8")

            # Create .bbl only
            (Path(tmpdir) / "physics.bbl").write_text(
                r"\begin{thebibliography}{1}\bibitem{einstein1905}Einstein\end{thebibliography}",
                encoding="utf-8",
            )

            parser = LaTeXParser()
            doc = parser.parse_file(str(tex_path))

            # Verify placeholders were created
            ph_str = str(doc.global_placeholders)
            assert "CITE" in ph_str or "REF" in ph_str or "MATH" in ph_str, (
                "Should have placeholders"
            )

            # Mock translate with special chars (no placeholder assumptions)
            translated_chunks = {}
            for chunk in doc.chunks:
                if "efficiency" in chunk.content:
                    translated_chunks[chunk.id] = "方程展示了 100% 的相关性"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify all elements preserved
            assert r"$E=mc^2$" in reconstructed, "Math should be preserved"
            assert r"\cite{einstein1905}" in reconstructed, (
                "Citation should be preserved"
            )
            assert r"\ref{eq:main}" in reconstructed, "Reference should be preserved"
            assert r"\begin{equation}" in reconstructed, (
                "Equation env should be preserved"
            )
            assert r"100\%" in reconstructed, "Percent should be escaped"
            assert r"\input{physics.bbl}" in reconstructed, (
                "Bibliography should be replaced"
            )


class TestPlaceholderIntegrity:
    """Test that placeholders survive the full pipeline intact."""

    def test_placeholder_survives_with_translation(self):
        """Placeholders should survive parse → translate → reconstruct."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Introduction}
See \cite{key2020} for the solution.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Verify placeholder was created
            assert len(doc.global_placeholders) > 0, "Should have global placeholders"
            cite_placeholders = [
                k for k in doc.global_placeholders.keys() if "CITE" in k
            ]
            assert len(cite_placeholders) > 0, "Should have CITE placeholder"

            # Mock translate with placeholder reference and special char
            translated_chunks = {}
            for chunk in doc.chunks:
                if "solution" in chunk.content:
                    # Keep placeholder reference in translation
                    translated_chunks[chunk.id] = "参见 [[CITE_1]] 了解 50% 的解决方案"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify placeholder was restored
            assert r"\cite{key2020}" in reconstructed, (
                f"Citation placeholder should be restored.\n"
                f"Reconstructed: {reconstructed}"
            )
            assert "[[CITE_" not in reconstructed, "Placeholder markers should be gone"
            assert r"50\%" in reconstructed, "Percent should be escaped"
        finally:
            Path(temp_path).unlink()

    def test_multiple_placeholder_types_survive(self):
        """All placeholder types (cite, ref, math, etc.) should survive."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Overview}
Equation $x=y$ in \cite{ref1} and \ref{eq:1} with good results.
\label{sec:overview}
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Verify placeholders exist
            ph_str = str(doc.global_placeholders)
            assert any(p in ph_str for p in ["CITE", "REF", "MATH", "LABEL"]), (
                "Should have various placeholder types"
            )

            # Mock translate with special chars (no placeholder assumptions)
            translated_chunks = {}
            for chunk in doc.chunks:
                if "results" in chunk.content:
                    translated_chunks[chunk.id] = "方程在文献中，25% & 50% 结果"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify all placeholders restored (by checking originals are back)
            assert r"$x=y$" in reconstructed, "Math should be restored"
            assert r"\cite{ref1}" in reconstructed, "Citation should be restored"
            assert r"\ref{eq:1}" in reconstructed, "Reference should be restored"
            assert r"\label{sec:overview}" in reconstructed, "Label should be restored"
            assert r"25\%" in reconstructed, "25% should be escaped"
            assert r"50\%" in reconstructed, "50% should be escaped"
            assert r"\&" in reconstructed, "Ampersand should be escaped"
        finally:
            Path(temp_path).unlink()

    def test_nested_placeholders_survive(self):
        """Nested placeholders (footnote containing cite) should survive."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Note}
Important fact here with details.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Mock translate with footnote-like content containing cite
            translated_chunks = {}
            for chunk in doc.chunks:
                if "details" in chunk.content:
                    translated_chunks[chunk.id] = "重要内容参见 [[CITE_1]] 了解100%细节"

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify special chars escaped
            assert r"100\%" in reconstructed, "Percent should be escaped"
        finally:
            Path(temp_path).unlink()


class TestRealWorldScenario:
    """Test real-world complex LaTeX documents."""

    def test_full_academic_paper_structure(self):
        """Complete academic paper with all elements."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_content = r"""\documentclass[11pt,a4paper]{article}
\usepackage{amsmath,amsfonts}

\title{Analysis of Efficiency Gain}
\author{Jane Smith}

\begin{document}
\maketitle

\begin{abstract}
We analyze the performance gains in detail.
\end{abstract}

\section{Introduction}\label{sec:intro}
The study of $E=mc^2$ and \cite{einstein1905} shows strong correlation.
As discussed in \ref{sec:method}, we use equation:
\begin{equation}\label{eq:main}
x = y + z
\end{equation}

\section{Methodology}\label{sec:method}
\subsection{Setup}
Our test achieved top ranking with high confidence.

\begin{itemize}
\item Item 1: Major improvement
\item Item 2: Significant gain
\end{itemize}

\section{Conclusion}
Results show \cite{ref1,ref2} validate our approach.

\bibliographystyle{plain}
\bibliography{references}
\end{document}"""

            tex_path = Path(tmpdir) / "paper.tex"
            tex_path.write_text(tex_content, encoding="utf-8")

            # Create .bbl file
            (Path(tmpdir) / "references.bbl").write_text(
                r"""\begin{thebibliography}{2}
\bibitem{einstein1905}Einstein, A. (1905).
\bibitem{ref1}Reference 1.
\bibitem{ref2}Reference 2.
\end{thebibliography}""",
                encoding="utf-8",
            )

            parser = LaTeXParser()
            doc = parser.parse_file(str(tex_path))

            # Mock translate various parts with special chars
            translated_chunks = {}
            for chunk in doc.chunks:
                content = chunk.content
                # Translate specific sections with special chars
                if "performance gains" in content:
                    translated_chunks[chunk.id] = "我们分析了 25% 和 50% 的性能提升"
                elif "correlation" in content:
                    translated_chunks[chunk.id] = "文献展示了 100% 的相关性"
                elif "ranking" in content:
                    translated_chunks[chunk.id] = (
                        "我们的 A & B 测试获得了 #1 排名和 75% 置信度"
                    )
                elif "Major improvement" in content:
                    translated_chunks[chunk.id] = "50% 改进"
                elif "Significant gain" in content:
                    translated_chunks[chunk.id] = "25% 增益"
                else:
                    translated_chunks[chunk.id] = content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify structure preserved
            assert r"\documentclass[11pt,a4paper]{article}" in reconstructed
            assert r"\title{" in reconstructed
            assert r"\author{" in reconstructed
            assert r"\begin{abstract}" in reconstructed
            assert r"\section{Introduction}" in reconstructed
            assert r"\label{sec:intro}" in reconstructed
            assert r"\subsection{Setup}" in reconstructed
            assert r"\begin{itemize}" in reconstructed
            assert r"\end{itemize}" in reconstructed

            # Verify placeholders restored
            assert r"$E=mc^2$" in reconstructed, "Math should be restored"
            assert r"\cite{einstein1905}" in reconstructed, (
                "Citation should be restored"
            )
            assert r"\ref{sec:method}" in reconstructed, "Reference should be restored"
            assert r"\label{eq:main}" in reconstructed, "Label should be restored"
            assert r"\begin{equation}" in reconstructed, (
                "Equation env should be restored"
            )

            # Verify special chars escaped
            assert r"25\%" in reconstructed, "25% should be escaped"
            assert r"50\%" in reconstructed, "50% should be escaped"
            assert r"100\%" in reconstructed, "100% should be escaped"
            assert r"75\%" in reconstructed, "75% should be escaped"
            assert r"\&" in reconstructed, "Ampersand should be escaped"
            assert r"\#" in reconstructed, "Hash should be escaped"

            # Verify bibliography replaced
            assert r"\input{references.bbl}" in reconstructed, (
                "Bibliography should be replaced with input"
            )

    def test_complex_math_with_special_chars(self):
        """Math environments with surrounding text containing special chars."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Math}
The formula shows results.
\begin{align}
x &= y + z \\
a & b = c
\end{align}
This is the final result.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Mock translate
            translated_chunks = {}
            for chunk in doc.chunks:
                if "final result" in chunk.content:
                    translated_chunks[chunk.id] = "这是 100% 和 #1 结果"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify math preserved
            assert r"\begin{align}" in reconstructed, (
                "Align environment should be preserved"
            )
            assert r"\end{align}" in reconstructed

            # Verify special chars escaped in translated text
            assert r"100\%" in reconstructed, "Percent should be escaped"
            assert r"\#" in reconstructed, "Hash should be escaped"
        finally:
            Path(temp_path).unlink()

    def test_footnotes_and_captions(self):
        """Complex document with footnotes and captions."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tex_content = r"""\documentclass{article}
\begin{document}
\section{Figures}
\begin{figure}
\centering
\includegraphics{fig.png}
\caption{Results showing improvement metrics.}
\label{fig:results}
\end{figure}

See Figure~\ref{fig:results} for details.
\end{document}"""

            tex_path = Path(tmpdir) / "fig.tex"
            tex_path.write_text(tex_content, encoding="utf-8")

            parser = LaTeXParser()
            doc = parser.parse_file(str(tex_path))

            # Mock translate
            translated_chunks = {}
            for chunk in doc.chunks:
                if "improvement" in chunk.content:
                    translated_chunks[chunk.id] = "结果显示 50% 和 25% 的改进"
                elif "details" in chunk.content:
                    translated_chunks[chunk.id] = "详见 [[REF_1]]，具有 100% 准确性"
                else:
                    translated_chunks[chunk.id] = chunk.content

            reconstructed = doc.reconstruct(translated_chunks)

            # Verify figure structure
            assert r"\begin{figure}" in reconstructed
            assert r"\end{figure}" in reconstructed
            assert r"\centering" in reconstructed
            assert r"\includegraphics{fig.png}" in reconstructed
            assert r"\caption{" in reconstructed
            assert r"\label{fig:results}" in reconstructed

            # Verify placeholders
            assert r"\ref{fig:results}" in reconstructed, (
                "Figure ref should be restored"
            )

            # Verify special chars escaped
            assert r"50\%" in reconstructed, "50% should be escaped"
            assert r"25\%" in reconstructed, "25% should be escaped"
            assert r"100\%" in reconstructed, "100% should be escaped"


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_translation_dict(self):
        """Empty translation dict should not cause errors."""
        test_content = r"""\documentclass{article}
\begin{document}
Test content.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Pass empty dict
            reconstructed = doc.reconstruct({})

            # Should still work
            assert r"\documentclass{article}" in reconstructed
            assert "Test content" in reconstructed
        finally:
            Path(temp_path).unlink()

    def test_partial_translation(self):
        """Partial translation (some chunks, not all)."""
        test_content = r"""\documentclass{article}
\begin{document}
\section{Intro}
First paragraph with data analysis.

Second paragraph with results summary.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Only translate one chunk with special chars
            translated_chunks = {}
            for chunk in doc.chunks:
                if "analysis" in chunk.content:
                    translated_chunks[chunk.id] = "数据分析显示 50% 改进"

            reconstructed = doc.reconstruct(translated_chunks)

            # Should work with partial translation
            assert r"50\%" in reconstructed, "50% should be escaped in translated chunk"
        finally:
            Path(temp_path).unlink()

    def test_already_escaped_chars_not_double_escaped(self):
        """Already escaped chars should not be double-escaped."""
        test_content = r"""\documentclass{article}
\begin{document}
Original has \% and \& already escaped.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # No translation - original should pass through unchanged
            reconstructed = doc.reconstruct(None)

            # Original already-escaped chars should not be double-escaped
            assert r"\%" in reconstructed, "Already escaped percent should stay as-is"
            assert r"\&" in reconstructed, "Already escaped ampersand should stay as-is"
            assert r"\\%" not in reconstructed, "Should not double-escape"
        finally:
            Path(temp_path).unlink()

    def test_special_chars_in_protected_context(self):
        """Special chars in protected chunks should not be escaped."""
        test_content = r"""\documentclass{article}
\begin{document}
\author{John Doe}
Some text here.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(test_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Protected chunks should NOT be escaped even if translated
            reconstructed = doc.reconstruct(None)

            # Author block should be preserved
            assert r"\author{John Doe}" in reconstructed, (
                "Author block should be preserved"
            )
        finally:
            Path(temp_path).unlink()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
