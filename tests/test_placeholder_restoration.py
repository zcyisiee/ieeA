"""Tests for global placeholder restoration in LaTeX documents."""

import pytest
from pathlib import Path
import tempfile
from ieeA.parser.latex_parser import LaTeXParser
from ieeA.parser.structure import LaTeXDocument, Chunk


class TestPlaceholderRestoration:
    """Test global placeholder restoration in LaTeX documents."""

    def test_single_placeholder_types(self):
        """Test that each placeholder type is correctly restored."""
        # Test cases using _replace_with_placeholder (stored in global_placeholders)
        global_placeholder_cases = [
            (r"See \cite{smith2020}", "CITE", r"\cite{smith2020}"),
            (r"In equation \ref{eq:1}", "REF", r"\ref{eq:1}"),
            (r"The formula $E=mc^2$ shows", "MATH", r"$E=mc^2$"),
            (r"Display \[x^2 + y^2 = z^2\] here", "MATH", r"\[x^2 + y^2 = z^2\]"),
            (
                r"\begin{equation}x=y\end{equation}",
                "MATHENV",
                r"\begin{equation}x=y\end{equation}",
            ),
            (r"\includegraphics{fig.png}", "GRAPHICS", r"\includegraphics{fig.png}"),
            (r"Text \label{sec:intro} more", "LABEL", r"\label{sec:intro}"),
            (r"Note\footnote{Important!} here", "FOOTNOTE", r"\footnote{Important!}"),
        ]

        for latex_content, placeholder_type, expected in global_placeholder_cases:
            full_doc = f"""\\documentclass{{article}}
\\begin{{document}}
{latex_content}
\\end{{document}}"""

            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".tex", delete=False
            ) as f:
                f.write(full_doc)
                temp_path = f.name

            try:
                parser = LaTeXParser()
                doc = parser.parse_file(temp_path)

                # Verify placeholder was created in global_placeholders
                assert len(doc.global_placeholders) > 0, (
                    f"No global placeholders created for {placeholder_type}"
                )

                # Reconstruct without translation
                reconstructed = doc.reconstruct()

                # Verify original LaTeX command is restored
                assert expected in reconstructed, (
                    f"Failed to restore {placeholder_type}: "
                    f"expected '{expected}' in reconstructed text"
                )
            finally:
                Path(temp_path).unlink()

        # Test case using _protect_author_block (stored in chunk.preserved_elements)
        # This is a special case - author block is protected as a chunk
        author_doc = r"""\documentclass{article}
\begin{document}
\author{John Doe}
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(author_doc)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Author block is stored in chunk's preserved_elements, not global_placeholders
            author_found = False
            for chunk in doc.chunks:
                if "AUTHOR" in str(chunk.preserved_elements):
                    author_found = True
                    break

            assert author_found, (
                "AUTHOR placeholder should be in chunk.preserved_elements"
            )

            # Reconstruct without translation
            reconstructed = doc.reconstruct()

            # Verify original LaTeX command is restored
            assert r"\author{John Doe}" in reconstructed, (
                f"Failed to restore AUTHOR: expected '\\author{{John Doe}}' in reconstructed text"
            )
        finally:
            Path(temp_path).unlink()

    def test_multiple_placeholders(self):
        """Test multiple placeholders of same and different types."""
        # Multiple same type
        same_type_doc = r"""
\documentclass{article}
\begin{document}
See \cite{ref1} and \cite{ref2} and \cite{ref3}.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(same_type_doc)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            assert len(doc.global_placeholders) == 3, "Should have 3 cite placeholders"

            reconstructed = doc.reconstruct()
            assert r"\cite{ref1}" in reconstructed
            assert r"\cite{ref2}" in reconstructed
            assert r"\cite{ref3}" in reconstructed
        finally:
            Path(temp_path).unlink()

        # Multiple different types
        mixed_doc = r"""
\documentclass{article}
\begin{document}
\section{Introduction}\label{sec:intro}
The equation $E=mc^2$ is referenced in \cite{einstein1905}.
See equation \ref{eq:1} below.
\begin{equation}\label{eq:1}
F = ma
\end{equation}
Note\footnote{This is important!} the result.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(mixed_doc)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Should have multiple different placeholder types
            assert len(doc.global_placeholders) >= 5, (
                "Should have at least 5 placeholders (cite, ref, math, mathenv, footnote, labels)"
            )

            reconstructed = doc.reconstruct()
            assert r"\cite{einstein1905}" in reconstructed
            assert r"\ref{eq:1}" in reconstructed
            assert r"$E=mc^2$" in reconstructed
            assert r"\begin{equation}" in reconstructed
            assert r"\label{sec:intro}" in reconstructed
            assert r"\label{eq:1}" in reconstructed
            assert r"\footnote{This is important!}" in reconstructed
        finally:
            Path(temp_path).unlink()

    def test_full_document_parsing(self):
        """Test parsing and reconstructing a full document."""
        full_doc = r"""
\documentclass{article}
\usepackage{amsmath}
\title{Test Document}
\author{Jane Smith}

\begin{document}
\maketitle

\section{Introduction}\label{sec:intro}
This paper discusses the theory in \cite{author2020}.

The main equation is:
\begin{equation}\label{eq:main}
x^2 + y^2 = z^2
\end{equation}

As shown in equation \ref{eq:main}, we have $x^2 + y^2 = z^2$.

\section{Conclusion}
See Section \ref{sec:intro} for details\footnote{More info available online.}.

\includegraphics{figure1.png}

\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(full_doc)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Verify placeholders were created
            assert len(doc.global_placeholders) > 0, "Should have placeholders"

            # Reconstruct
            reconstructed = doc.reconstruct()

            # Verify all key elements are preserved
            assert r"\documentclass{article}" in reconstructed
            assert r"\author{Jane Smith}" in reconstructed
            assert r"\cite{author2020}" in reconstructed
            assert r"\label{sec:intro}" in reconstructed
            assert r"\label{eq:main}" in reconstructed
            assert r"\ref{eq:main}" in reconstructed
            assert r"\ref{sec:intro}" in reconstructed
            assert r"$x^2 + y^2 = z^2$" in reconstructed
            assert r"\begin{equation}" in reconstructed
            assert r"\footnote{More info available online.}" in reconstructed
            assert r"\includegraphics{figure1.png}" in reconstructed
        finally:
            Path(temp_path).unlink()

    def test_nested_placeholders(self):
        """Test nested placeholders like footnote containing cite."""
        nested_doc = r"""
\documentclass{article}
\begin{document}
This is a fact\footnote{See \cite{source2023} for details.} in the text.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(nested_doc)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Should have both footnote and cite placeholders in global_placeholders
            assert len(doc.global_placeholders) >= 2, (
                f"Should have placeholders for both footnote and cite, got: {doc.global_placeholders}"
            )

            # Verify we have the expected types
            placeholders_str = str(doc.global_placeholders)
            assert "FOOTNOTE" in placeholders_str, "Should have FOOTNOTE placeholder"
            assert "CITE" in placeholders_str, "Should have CITE placeholder"

            reconstructed = doc.reconstruct()

            # The nested structure should be preserved
            # The footnote should contain the cite
            assert r"\footnote{" in reconstructed, "Footnote should be restored"
            assert r"\cite{source2023}" in reconstructed, (
                "Cite inside footnote should be restored"
            )

            # Verify the nested structure is intact
            # This is a more robust check - find footnote and verify cite is inside it
            import re

            footnote_pattern = r"\\footnote\{[^}]*\\cite\{source2023\}[^}]*\}"
            assert re.search(footnote_pattern, reconstructed), (
                f"Nested cite inside footnote should be preserved. Reconstructed: {reconstructed[:500]}"
            )
        finally:
            Path(temp_path).unlink()

    def test_translated_chunks(self):
        """Test reconstruction with translated chunk content."""
        original_doc = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
This paper reviews \cite{smith2020} and discusses $E=mc^2$.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(original_doc)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Simulate translation by modifying chunk content
            # The English text "This paper reviews" -> "本文综述"
            for chunk in doc.chunks:
                if "This paper reviews" in chunk.content:
                    # Replace English with Chinese, keeping placeholders
                    chunk.content = chunk.content.replace(
                        "This paper reviews", "本文综述"
                    ).replace("and discusses", "并讨论")

            # Reconstruct
            reconstructed = doc.reconstruct()

            # Verify translation is present
            assert "本文综述" in reconstructed, "Translation should be in output"
            assert "并讨论" in reconstructed, "Translation should be in output"

            # Verify placeholders are restored
            assert r"\cite{smith2020}" in reconstructed, "Cite should be restored"
            assert r"$E=mc^2$" in reconstructed, "Math should be restored"

            # Verify structure is maintained
            assert r"\section{Introduction}" in reconstructed
        finally:
            Path(temp_path).unlink()

    def test_empty_document(self):
        """Test edge cases with empty documents."""
        # Empty document
        empty_doc = r"""
\documentclass{article}
\begin{document}
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(empty_doc)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Should have no placeholders
            assert len(doc.global_placeholders) == 0, (
                "Empty doc should have no placeholders"
            )

            # Should still reconstruct successfully
            reconstructed = doc.reconstruct()
            assert r"\documentclass{article}" in reconstructed
            assert r"\begin{document}" in reconstructed
            assert r"\end{document}" in reconstructed
        finally:
            Path(temp_path).unlink()

        # Document with no placeholders
        no_placeholders_doc = r"""
\documentclass{article}
\begin{document}
\section{Introduction}
This is plain text with no special commands.
Just regular paragraphs.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(no_placeholders_doc)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # Should have no placeholders
            assert len(doc.global_placeholders) == 0, (
                "No placeholder doc should have no placeholders"
            )

            # Should reconstruct exactly
            reconstructed = doc.reconstruct()
            assert "This is plain text with no special commands." in reconstructed
            assert "Just regular paragraphs." in reconstructed
        finally:
            Path(temp_path).unlink()

    def test_placeholder_uniqueness(self):
        """Test that placeholder IDs are unique across the document."""
        doc_content = r"""
\documentclass{article}
\begin{document}
Text with \cite{ref1} and \cite{ref2}.
Math: $x=1$ and $y=2$.
\ref{eq:1} and \ref{eq:2}.
\end{document}"""

        with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(doc_content)
            temp_path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(temp_path)

            # All placeholder keys should be unique
            placeholder_keys = list(doc.global_placeholders.keys())
            assert len(placeholder_keys) == len(set(placeholder_keys)), (
                "All placeholder keys should be unique"
            )

            # Verify we have the expected types
            placeholder_types = [key.split("_")[0] for key in placeholder_keys]
            assert "[[CITE" in " ".join(placeholder_keys), (
                "Should have CITE placeholders"
            )
            assert "[[MATH" in " ".join(placeholder_keys), (
                "Should have MATH placeholders"
            )
            assert "[[REF" in " ".join(placeholder_keys), "Should have REF placeholders"
        finally:
            Path(temp_path).unlink()
