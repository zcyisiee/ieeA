import re
from pathlib import Path

from ieeA.parser.latex_parser import LaTeXParser


def _has_prefix(keys: list[str], prefix: str) -> bool:
    return any(key.startswith(f"[[{prefix}_") for key in keys)


def test_universal_corpus_parses_and_reconstructs():
    corpus_path = Path(__file__).resolve().parent / "universal" / "universal.tex"
    parser = LaTeXParser()
    doc = parser.parse_file(str(corpus_path))

    assert doc.chunks, "Expected chunks from universal corpus"
    assert "{{CHUNK_" in doc.body_template, "Expected chunk placeholders in body"

    chunk_ids_in_preamble = set(re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", doc.preamble))
    chunk_ids_in_body = set(
        re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", doc.body_template)
    )
    nested_chunk_ids = set()
    for chunk in doc.chunks:
        nested_chunk_ids.update(re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", chunk.content))
    global_placeholder_chunk_ids = set()
    for original in doc.global_placeholders.values():
        global_placeholder_chunk_ids.update(
            re.findall(r"\{\{CHUNK_([a-f0-9-]+)\}\}", original)
        )
    all_placeholder_ids = (
        chunk_ids_in_preamble
        | chunk_ids_in_body
        | nested_chunk_ids
        | global_placeholder_chunk_ids
    )
    chunk_ids_created = {c.id for c in doc.chunks}
    protected_chunk_ids = {c.id for c in doc.chunks if c.context == "protected"}

    orphan_ids = chunk_ids_created - all_placeholder_ids - protected_chunk_ids
    assert not orphan_ids, f"Orphan chunks without placeholders: {orphan_ids}"

    reconstructed = doc.reconstruct()
    assert "{{CHUNK_" not in reconstructed, "Unreplaced chunk placeholders remain"

    placeholder_keys = list(doc.global_placeholders.keys())
    expected_prefixes = [
        "MATH",
        "ENV",
        "CITE",
        "REF",
        "LABEL",
        "URL",
        "HREF",
        "GRAPHICS",
    ]
    missing_prefixes = [
        p for p in expected_prefixes if not _has_prefix(placeholder_keys, p)
    ]
    assert not missing_prefixes, f"Missing placeholder types: {missing_prefixes}"

    contexts = {c.context for c in doc.chunks}
    expected_contexts = {
        "title",
        "section",
        "abstract",
        "itemize",
        "caption",
        "footnote",
        "paragraph",
    }
    missing_contexts = expected_contexts - contexts
    assert not missing_contexts, f"Missing chunk contexts: {missing_contexts}"

    assert "This content comes from extra.tex" in reconstructed
