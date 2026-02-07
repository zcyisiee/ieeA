import re

from ieeA.parser.latex_parser import LaTeXParser


def test_process_body_uses_refactored_stage_order(monkeypatch):
    parser = LaTeXParser()
    order = []

    def stage(name):
        def _impl(text):
            order.append(name)
            return f"{text}<{name}>"

        return _impl

    # New stage names should be used by _process_body
    monkeypatch.setattr(parser, "_extract_pre_protection_chunks", stage("pre"), raising=False)
    monkeypatch.setattr(parser, "_protect_environments", stage("env"), raising=False)
    monkeypatch.setattr(parser, "_protect_inline_math", stage("inline_math"), raising=True)
    monkeypatch.setattr(parser, "_protect_commands", stage("commands"), raising=True)
    monkeypatch.setattr(parser, "_extract_translatable_text", stage("extract_text"), raising=False)

    # Deprecated names should not be used in the new flow
    def deprecated(_text):
        raise AssertionError("Deprecated stage was called")

    monkeypatch.setattr(parser, "_protect_math_environments", deprecated, raising=True)
    monkeypatch.setattr(parser, "_extract_translatable_content", deprecated, raising=True)

    result = parser._process_body("seed")

    assert order == ["pre", "env", "inline_math", "commands", "extract_text"]
    assert result.endswith("<extract_text>")


def test_extract_pre_protection_chunks_handles_author_and_caption():
    parser = LaTeXParser()

    text = r"""
\\author{Alice and Bob}
\\begin{figure}
\\caption{This caption is definitely longer than ten chars}
\\end{figure}
"""

    processed = parser._extract_pre_protection_chunks(text)

    assert "[[AUTHOR_" in processed
    assert re.search(r"\{\{CHUNK_[a-f0-9-]+\}\}", processed)

    contexts = {chunk.context for chunk in parser.chunks}
    assert "protected" in contexts
    assert "caption" in contexts


def test_protect_environments_shields_inline_math_inside_algorithm():
    parser = LaTeXParser()

    text = r"""
\\begin{algorithm}
\\STATE $x = 1$
\\end{algorithm}
Outside math: $y = 2$
"""

    stage1 = parser._extract_pre_protection_chunks(text)
    stage2 = parser._protect_environments(stage1)
    stage3 = parser._protect_inline_math(stage2)

    assert "[[MATHENV_" in stage2
    assert "[[MATH_" in stage3

    math_values = [
        v for k, v in parser.placeholder_map.items() if k.startswith("[[MATH_")
    ]
    assert any("$y = 2$" in value for value in math_values)
    assert all("algorithm" not in value for value in math_values)


def test_protect_inline_math_ignores_escaped_dollar_and_multiline_block():
    parser = LaTeXParser()

    text = "Price is \\$5, inline $a+b$, display $$x\n\n y$$ end"
    processed = parser._protect_inline_math(text)

    assert r"\$5" in processed
    assert "$$x\n\n y$$" in processed
    assert "[[MATH_" in processed

    math_values = [
        v for k, v in parser.placeholder_map.items() if k.startswith("[[MATH_")
    ]
    assert any("$a+b$" in value for value in math_values)
    assert all("$$x\n\n y$$" not in value for value in math_values)


def test_protect_environments_respects_extra_protected_envs():
    parser = LaTeXParser(extra_protected_envs=["myenv"])

    text = r"""
Before
\\begin{myenv}
secret content
\\end{myenv}
After
"""

    processed = parser._protect_environments(text)

    assert "[[MATHENV_" in processed
    assert any(
        "\\begin{myenv}" in value for value in parser.placeholder_map.values()
    )


def test_extract_translatable_text_creates_expected_chunks():
    parser = LaTeXParser()

    text = r"""
\\section{Introduction}
This paragraph is intentionally long enough to be extracted as a translatable chunk for robust parser testing.
"""

    processed = parser._extract_translatable_text(text)

    assert "{{CHUNK_" in processed
    contexts = {chunk.context for chunk in parser.chunks}
    assert "section" in contexts
    assert "paragraph" in contexts
