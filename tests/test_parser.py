import pytest
import os
from tempfile import NamedTemporaryFile, TemporaryDirectory
from src.ieet.parser.structure import Chunk, LaTeXDocument
from src.ieet.parser.chunker import LatexChunker
from src.ieet.parser.latex_parser import LaTeXParser
from pylatexenc.latexwalker import LatexWalker, get_default_latex_context_db


class TestChunker:
    def test_simple_text_chunking(self):
        latex = "This is a paragraph.\n\nThis is another paragraph."
        walker = LatexWalker(latex, latex_context=get_default_latex_context_db())
        nodes, _, _ = walker.get_latex_nodes()

        chunker = LatexChunker()
        chunks = chunker.chunk_nodes(nodes)

        assert len(chunks) == 2
        assert chunks[0].content.strip() == "This is a paragraph."
        assert chunks[1].content.strip() == "This is another paragraph."

    def test_protected_commands(self):
        latex = r"This has a citation \cite{ref1} and math $x=y$."
        walker = LatexWalker(latex, latex_context=get_default_latex_context_db())
        nodes, _, _ = walker.get_latex_nodes()

        chunker = LatexChunker()
        chunks = chunker.chunk_nodes(nodes)

        assert len(chunks) == 1
        content = chunks[0].content
        # Check for placeholders
        assert "[[REF_" in content
        assert "[[MATH_" in content
        assert "citation" in content

        # Verify reconstruction
        reconstructed = chunks[0].reconstruct()
        assert r"\cite{ref1}" in reconstructed
        assert r"$x=y$" in reconstructed

    def test_section_titles(self):
        latex = r"\section{Introduction} This is the intro."
        walker = LatexWalker(latex, latex_context=get_default_latex_context_db())
        nodes, _, _ = walker.get_latex_nodes()

        chunker = LatexChunker()
        chunks = chunker.chunk_nodes(nodes)

        # Expected: Section chunk, then text chunk
        assert len(chunks) >= 2
        assert chunks[0].context == "section"
        assert chunks[0].content == "Introduction"
        assert chunks[0].reconstruct() == r"\section{Introduction}"

        assert chunks[1].context == "paragraph"
        assert "This is the intro" in chunks[1].content

    def test_nested_formatting(self):
        latex = r"This is \textbf{bold} text."
        walker = LatexWalker(latex, latex_context=get_default_latex_context_db())
        nodes, _, _ = walker.get_latex_nodes()

        chunker = LatexChunker()
        chunks = chunker.chunk_nodes(nodes)

        assert len(chunks) == 1
        # Expect verbatim for textbf
        assert r"\textbf{bold}" in chunks[0].content


class TestLaTeXParser:
    def test_flattening(self):
        with TemporaryDirectory() as tmpdir:
            main_tex = os.path.join(tmpdir, "main.tex")
            sub_tex = os.path.join(tmpdir, "sub.tex")

            with open(sub_tex, "w") as f:
                f.write("Content from sub file.")

            with open(main_tex, "w") as f:
                f.write(r"Main content. \input{sub} End main.")

            parser = LaTeXParser()
            doc = parser.parse_file(main_tex)

            full_text = doc.reconstruct()
            assert "Content from sub file" in full_text
            assert "Main content" in full_text

    def test_preamble_separation(self):
        latex = r"""\documentclass{article}
\usepackage{test}
\begin{document}
Hello world. This is a longer sentence to ensure it gets chunked properly by the parser.
\end{document}"""

        with NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
            f.write(latex)
            path = f.name

        try:
            parser = LaTeXParser()
            doc = parser.parse_file(path)

            assert r"\documentclass{article}" in doc.preamble
            assert r"\begin{document}" in doc.preamble
            # Body should contain "Hello world."
            # Depending on how we chunks, check content
            found_hello = False
            for chunk in doc.chunks:
                if "Hello world" in chunk.content:
                    found_hello = True
            assert found_hello

        finally:
            os.remove(path)
