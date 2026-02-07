import re
import tempfile
from pathlib import Path

from ieeA.parser.latex_parser import LaTeXParser


def _parse_tex(content: str):
    parser = LaTeXParser()
    with tempfile.NamedTemporaryFile(mode="w", suffix=".tex", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        doc = parser.parse_file(path)
        return parser, doc
    finally:
        Path(path).unlink()


def _title_chunks(doc):
    return [c for c in doc.chunks if c.context == "title"]


def _suspicious_preamble_macro_chunks(doc):
    suspicious = []
    for chunk in doc.chunks:
        if chunk.context != "paragraph":
            continue
        text = chunk.content
        if any(token in text for token in (r"\newcommand", r"\def", r"\Declare")):
            suspicious.append(text)
    return suspicious


def test_section_commands_excludes_title():
    assert "title" not in LaTeXParser.SECTION_COMMANDS


def test_extract_title_command_handles_nested_braces():
    parser = LaTeXParser()
    parser.chunks = []

    text = (
        r"\title{A {Nested} Title with \textbf{Bold {Inner}} and $E=mc^2$}"
        "\n"
        r"\begin{document}"
    )
    processed = parser._extract_title_command(text)

    assert "{{CHUNK_" in processed
    titles = [c for c in parser.chunks if c.context == "title"]
    assert len(titles) == 1
    assert "Nested" in titles[0].content
    assert r"\textbf{Bold {Inner}}" in titles[0].content


def test_preamble_title_extracted_once():
    _, doc = _parse_tex(
        r"""
\documentclass{article}
\title{Preamble Title}
\begin{document}
\maketitle
\section{Intro}
Some body text that should become paragraph chunks.
\end{document}
"""
    )
    titles = _title_chunks(doc)
    assert len(titles) == 1
    assert titles[0].content == "Preamble Title"


def test_body_title_extracted_once():
    _, doc = _parse_tex(
        r"""
\documentclass{article}
\begin{document}
\title{Body Title}
\maketitle
Text for parser.
\end{document}
"""
    )
    titles = _title_chunks(doc)
    assert len(titles) == 1
    assert titles[0].content == "Body Title"


def test_preamble_and_body_titles_extracted_without_duplication():
    _, doc = _parse_tex(
        r"""
\documentclass{article}
\title{Preamble Title}
\begin{document}
\title{Body Title}
\maketitle
Body paragraph text here.
\end{document}
"""
    )
    contents = sorted(c.content for c in _title_chunks(doc))
    assert contents == ["Body Title", "Preamble Title"]


def test_legacy_extract_title_from_preamble_delegates_to_new_helper(monkeypatch):
    parser = LaTeXParser()

    calls = {"count": 0}

    def fake_extract(text: str) -> str:
        calls["count"] += 1
        return text + "\n%delegated"

    monkeypatch.setattr(parser, "_extract_title_command", fake_extract, raising=False)

    out = parser._extract_title_from_preamble(r"\title{X}")
    assert calls["count"] == 1
    assert out.endswith("%delegated")


def test_regression_no_preamble_macro_chunks_for_reference_corpora():
    corpus_files = [
        Path("output/hq/2504.19793/A-main.tex"),
        Path("output/hq/2511.16709/neurips_2025.tex"),
        Path("tests/universal/universal.tex"),
    ]

    for corpus in corpus_files:
        assert corpus.exists(), f"Missing regression corpus: {corpus}"
        parser = LaTeXParser()
        doc = parser.parse_file(str(corpus))

        suspicious = _suspicious_preamble_macro_chunks(doc)
        assert not suspicious, (
            f"Found suspicious preamble macro chunks in {corpus}: "
            f"{len(suspicious)} examples"
        )
        reconstructed = doc.reconstruct()
        assert not re.findall(r"\{\{CHUNK_[a-f0-9-]+\}\}", reconstructed)
