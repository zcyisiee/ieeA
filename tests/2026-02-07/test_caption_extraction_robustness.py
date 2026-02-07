import re

from ieeA.parser.latex_parser import LaTeXParser


def _extract_caption_chunks(text: str):
    parser = LaTeXParser()
    parser.chunks = []
    parser.protected_counter = 0
    parser.placeholder_map = {}
    processed = parser._extract_captions(text)
    captions = [c for c in parser.chunks if c.context == "caption"]
    return parser, processed, captions


def test_extract_basic_caption():
    _, processed, captions = _extract_caption_chunks(
        r"\caption{This is a sufficiently long caption text}"
    )
    assert len(captions) == 1
    assert captions[0].content == "This is a sufficiently long caption text"
    assert "{{CHUNK_" in processed


def test_extract_star_caption():
    _, processed, captions = _extract_caption_chunks(
        r"\caption*{This is a sufficiently long starred caption text}"
    )
    assert len(captions) == 1
    assert "starred caption text" in captions[0].content
    assert r"\caption*{" in processed


def test_extract_caption_with_optional_short():
    _, processed, captions = _extract_caption_chunks(
        r"\caption[Short]{This is a sufficiently long caption body}"
    )
    assert len(captions) == 1
    assert captions[0].content == "This is a sufficiently long caption body"
    assert "[Short]" in processed


def test_extract_captionof():
    _, processed, captions = _extract_caption_chunks(
        r"\captionof{figure}{This is a sufficiently long captionof body}"
    )
    assert len(captions) == 1
    assert captions[0].content == "This is a sufficiently long captionof body"
    assert r"\captionof{figure}" in processed
    assert "{{CHUNK_" in processed


def test_extract_caption_with_nested_optional_brackets():
    _, processed, captions = _extract_caption_chunks(
        r"\caption[Short [Nested]]{This is a sufficiently long caption body}"
    )
    assert len(captions) == 1
    assert captions[0].content == "This is a sufficiently long caption body"
    assert "[Short [Nested]]" in processed


def test_extract_caption_with_escaped_braces():
    _, processed, captions = _extract_caption_chunks(
        r"\caption{This contains literal \{ and \} braces and should be extracted}"
    )
    assert len(captions) == 1
    assert r"literal \{ and \} braces" in captions[0].content
    assert "{{CHUNK_" in processed


def test_no_extract_inside_verbatim():
    _, processed, captions = _extract_caption_chunks(
        r"""\begin{verbatim}
\caption{This is inside verbatim and should be ignored}
\end{verbatim}"""
    )
    assert len(captions) == 0
    assert r"\caption{This is inside verbatim and should be ignored}" in processed


def test_no_extract_inside_lstlisting():
    _, processed, captions = _extract_caption_chunks(
        r"""\begin{lstlisting}
\caption{This is inside lstlisting and should be ignored}
\end{lstlisting}"""
    )
    assert len(captions) == 0
    assert r"\caption{This is inside lstlisting and should be ignored}" in processed


def test_no_extract_inside_minted():
    _, processed, captions = _extract_caption_chunks(
        r"""\begin{minted}{tex}
\caption{This is inside minted and should be ignored}
\end{minted}"""
    )
    assert len(captions) == 0
    assert r"\caption{This is inside minted and should be ignored}" in processed


def test_empty_caption_not_extracted():
    _, _, captions = _extract_caption_chunks(r"\caption{}")
    assert len(captions) == 0


def test_existing_chunk_placeholder_not_reextracted():
    _, _, captions = _extract_caption_chunks(r"\caption{{{CHUNK_abc}}}")
    assert len(captions) == 0


def test_short_caption_now_extracted_without_length_threshold():
    _, processed, captions = _extract_caption_chunks(r"\caption{short}")
    assert len(captions) == 1
    assert captions[0].content == "short"
    assert re.search(r"\{\{CHUNK_[a-f0-9-]+\}\}", processed)
