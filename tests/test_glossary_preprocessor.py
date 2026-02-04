"""Tests for GlossaryPreprocessor - glossary term placeholder handling."""

import pytest
from ieeA.translator.pipeline import GlossaryPreprocessor
from ieeA.rules.glossary import Glossary, GlossaryEntry


class TestGlossaryPreprocessor:
    """Test glossary term preprocessing and postprocessing."""

    @pytest.fixture
    def simple_glossary(self):
        """Simple glossary with basic terms."""
        return Glossary.from_dict(
            {"Transformer": "Transformer", "MMLU": "MMLU", "attention": "注意力机制"}
        )

    @pytest.fixture
    def glossary_with_special_chars(self):
        """Glossary with special characters in terms."""
        return Glossary.from_dict(
            {"C++": "C++", "R^2": "R²", "self-attention": "自注意力"}
        )

    def test_preprocess_creates_gloss_placeholder(self, simple_glossary):
        """Test that preprocess creates [[GLOSS_xxx]] format placeholders."""
        preprocessor = GlossaryPreprocessor(simple_glossary)
        text = "The Transformer uses attention mechanism."

        result, mapping = preprocessor.preprocess(text)

        # Check placeholder format
        assert "[[GLOSS_001]]" in result
        assert "[[GLOSS_002]]" in result
        # Original terms should be replaced
        assert "Transformer" not in result
        assert "attention" not in result
        # Mapping should contain placeholders to original terms
        assert "Transformer" in mapping.values()
        assert "attention" in mapping.values()

    def test_postprocess_restores_glossary_terms(self, simple_glossary):
        """Test that postprocess replaces placeholders with glossary translations."""
        preprocessor = GlossaryPreprocessor(simple_glossary)
        text = "The Transformer uses attention mechanism."

        preprocessed, mapping = preprocessor.preprocess(text)
        restored = preprocessor.postprocess(preprocessed, mapping)

        # Should restore with translations
        assert "Transformer" in restored  # Kept as is (target is same)
        assert "注意力机制" in restored  # Translated
        # Placeholders should be gone
        assert "[[GLOSS_" not in restored

    def test_preprocess_postprocess_roundtrip(self, simple_glossary):
        """Test that preprocess→postprocess maintains consistency."""
        preprocessor = GlossaryPreprocessor(simple_glossary)
        original = "MMLU benchmark evaluates Transformer models."

        preprocessed, mapping = preprocessor.preprocess(original)
        restored = preprocessor.postprocess(preprocessed, mapping)

        # After round-trip, terms should be replaced with their targets
        assert "MMLU" in restored  # Target is "MMLU"
        assert "Transformer" in restored  # Target is "Transformer"
        # No placeholders left
        assert "[[GLOSS_" not in restored

    def test_multiple_glossary_terms(self, simple_glossary):
        """Test handling multiple glossary terms in same text."""
        preprocessor = GlossaryPreprocessor(simple_glossary)
        text = "Transformer attention Transformer MMLU attention"

        preprocessed, mapping = preprocessor.preprocess(text)

        # Should create multiple placeholders
        assert (
            preprocessed.count("[[GLOSS_") == 5
        )  # 2 Transformer + 2 attention + 1 MMLU
        assert len(mapping) == 5

        # Restore should work correctly
        restored = preprocessor.postprocess(preprocessed, mapping)
        assert restored.count("Transformer") == 2
        assert restored.count("注意力机制") == 2
        assert restored.count("MMLU") == 1

    def test_empty_text(self, simple_glossary):
        """Test edge case with empty text."""
        preprocessor = GlossaryPreprocessor(simple_glossary)

        result, mapping = preprocessor.preprocess("")

        assert result == ""
        assert mapping == {}

        # Postprocess should also handle empty
        restored = preprocessor.postprocess("", {})
        assert restored == ""

    def test_special_characters_in_term(self, glossary_with_special_chars):
        """Test glossary terms with special characters like C++."""
        preprocessor = GlossaryPreprocessor(glossary_with_special_chars)
        text = "C++ and R^2 with self-attention are important."

        preprocessed, mapping = preprocessor.preprocess(text)

        # Special characters should be escaped and matched
        assert "C++" not in preprocessed
        assert "R^2" not in preprocessed
        assert "self-attention" not in preprocessed
        assert "[[GLOSS_" in preprocessed

        # Restore should work
        restored = preprocessor.postprocess(preprocessed, mapping)
        assert "C++" in restored
        assert "R²" in restored
        assert "自注意力" in restored

    def test_no_glossary_terms_in_text(self, simple_glossary):
        """Test text with no glossary terms."""
        preprocessor = GlossaryPreprocessor(simple_glossary)
        text = "This is plain text without any terms."

        result, mapping = preprocessor.preprocess(text)

        assert result == text  # Should remain unchanged
        assert mapping == {}

    def test_case_sensitive_matching(self, simple_glossary):
        """Test that glossary matching is case-sensitive."""
        preprocessor = GlossaryPreprocessor(simple_glossary)
        text = "transformer and Transformer are different."

        preprocessed, mapping = preprocessor.preprocess(text)

        # Only exact case match should be replaced
        assert "transformer" in preprocessed  # lowercase not in glossary
        assert "Transformer" not in preprocessed  # should be replaced
        assert "[[GLOSS_" in preprocessed

    def test_placeholder_counter_increments(self, simple_glossary):
        """Test that placeholder counter increments correctly."""
        preprocessor = GlossaryPreprocessor(simple_glossary)

        # First preprocess
        text1 = "Transformer model"
        result1, mapping1 = preprocessor.preprocess(text1)
        assert "[[GLOSS_001]]" in result1

        # Second preprocess (counter should continue)
        text2 = "attention mechanism"
        result2, mapping2 = preprocessor.preprocess(text2)
        assert "[[GLOSS_002]]" in result2
        assert "[[GLOSS_001]]" not in result2

    def test_longest_match_first(self):
        """Test that longer terms are matched before shorter overlapping terms."""
        glossary = Glossary.from_dict(
            {"self": "自身", "self-attention": "自注意力", "attention": "注意力"}
        )
        preprocessor = GlossaryPreprocessor(glossary)
        text = "self-attention is better than attention"

        preprocessed, mapping = preprocessor.preprocess(text)

        # "self-attention" should be matched as one term, not "self" + "-" + "attention"
        term_list = list(mapping.values())
        assert "self-attention" in term_list
        # Should have 2 placeholders: "self-attention" and "attention"
        assert len(mapping) == 2

    def test_postprocess_with_missing_glossary_entry(self, simple_glossary):
        """Test postprocess fallback when glossary entry is missing."""
        preprocessor = GlossaryPreprocessor(simple_glossary)

        # Manually create mapping with a term not in glossary
        mapping = {"[[GLOSS_001]]": "UnknownTerm"}
        text = "This is [[GLOSS_001]] in text."

        result = preprocessor.postprocess(text, mapping)

        # Should fallback to original term
        assert "UnknownTerm" in result
        assert "[[GLOSS_001]]" not in result

    def test_whitespace_preservation(self, simple_glossary):
        """Test that whitespace is preserved during preprocess/postprocess."""
        preprocessor = GlossaryPreprocessor(simple_glossary)
        text = "The  Transformer  uses   attention   here."

        preprocessed, mapping = preprocessor.preprocess(text)
        restored = preprocessor.postprocess(preprocessed, mapping)

        # Multiple spaces should be preserved
        assert "  " in restored
        assert "   " in restored

    def test_newline_preservation(self, simple_glossary):
        """Test that newlines are preserved."""
        preprocessor = GlossaryPreprocessor(simple_glossary)
        text = "Transformer model\nuses attention\nmechanism"

        preprocessed, mapping = preprocessor.preprocess(text)
        restored = preprocessor.postprocess(preprocessed, mapping)

        # Newlines should be preserved
        assert "\n" in preprocessed
        assert "\n" in restored
        assert restored.count("\n") == 2
