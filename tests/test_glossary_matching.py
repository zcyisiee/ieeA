"""Tests for glossary word-boundary matching."""

import pytest
from unittest.mock import MagicMock
from ieeA.rules.glossary import Glossary, GlossaryEntry
from ieeA.translator.pipeline import TranslationPipeline


@pytest.fixture
def glossary():
    return Glossary(
        terms={
            "AI": GlossaryEntry(target="人工智能"),
            "CR": GlossaryEntry(target="CR"),
            "Transformer": GlossaryEntry(target="Transformer"),
            "C++": GlossaryEntry(target="C++"),
            "NLP": GlossaryEntry(target="自然语言处理"),
            "ASR": GlossaryEntry(target="自动语音识别"),
        }
    )


@pytest.fixture
def pipeline(glossary):
    provider = MagicMock()
    return TranslationPipeline(provider=provider, glossary=glossary)


class TestGlossaryWordBoundary:
    """Test that glossary matching uses word boundaries, not substring."""

    def test_substring_rejection_ai_in_brain(self, pipeline):
        """'AI' should NOT match inside 'brain'."""
        result = pipeline._build_glossary_hints("The brain is complex")
        assert "AI" not in result

    def test_substring_rejection_cr_in_across(self, pipeline):
        """'CR' should NOT match inside 'across'."""
        result = pipeline._build_glossary_hints("across the field")
        assert "CR" not in result

    def test_substring_rejection_asr_in_laser(self, pipeline):
        """'ASR' should NOT match inside 'laser'."""
        result = pipeline._build_glossary_hints("a laser beam")
        assert "ASR" not in result

    def test_normal_match_standalone_ai(self, pipeline):
        """'AI' should match when standalone."""
        result = pipeline._build_glossary_hints("AI is powerful")
        assert "AI" in result
        assert result["AI"] == "人工智能"

    def test_normal_match_multiple_terms(self, pipeline):
        """Multiple terms should match when standalone."""
        result = pipeline._build_glossary_hints("AI and NLP are important")
        assert "AI" in result
        assert "NLP" in result

    def test_case_insensitive(self, pipeline):
        """Matching should be case-insensitive."""
        result = pipeline._build_glossary_hints("ai is powerful")
        assert "AI" in result

    def test_cjk_boundary(self, pipeline):
        """'AI' should match at CJK boundaries."""
        result = pipeline._build_glossary_hints("让AI来做翻译")
        assert "AI" in result

    def test_regex_metacharacter_safety(self, pipeline):
        """Terms with regex metacharacters like 'C++' should work."""
        result = pipeline._build_glossary_hints("I love C++ programming")
        assert "C++" in result

    def test_empty_text(self, pipeline):
        """Empty text should return empty dict."""
        result = pipeline._build_glossary_hints("")
        assert result == {}

    def test_no_matching_terms(self, pipeline):
        """Text without any glossary terms should return empty dict."""
        result = pipeline._build_glossary_hints("The quick brown fox")
        assert result == {}

    def test_transformer_match(self, pipeline):
        """'Transformer' should match correctly."""
        result = pipeline._build_glossary_hints("The Transformer model is great")
        assert "Transformer" in result
