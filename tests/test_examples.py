"""Tests for few-shot examples loading."""

import pytest
from pathlib import Path
from ieeA.rules.examples import load_examples, load_builtin_examples


class TestLoadBuiltinExamples:
    """Tests for load_builtin_examples function."""

    def test_returns_list(self):
        """Verify function returns a list."""
        examples = load_builtin_examples()
        assert isinstance(examples, list)

    def test_has_minimum_examples(self):
        """Verify at least 3 examples are loaded."""
        examples = load_builtin_examples()
        assert len(examples) >= 3

    def test_examples_have_required_keys(self):
        """Verify each example has source and target keys."""
        examples = load_builtin_examples()
        for ex in examples:
            assert "source" in ex, "Example missing 'source' key"
            assert "target" in ex, "Example missing 'target' key"

    def test_examples_not_empty(self):
        """Verify examples have non-empty content."""
        examples = load_builtin_examples()
        for ex in examples:
            assert ex["source"], "Example has empty 'source'"
            assert ex["target"], "Example has empty 'target'"


class TestLoadExamples:
    """Tests for load_examples function."""

    def test_default_loads_builtin(self):
        """Verify default call loads built-in examples."""
        examples = load_examples()
        builtin = load_builtin_examples()
        assert len(examples) == len(builtin)

    def test_invalid_path_returns_builtin(self):
        """Verify invalid path falls back to built-in examples."""
        examples = load_examples("/nonexistent/path/examples.yaml")
        assert len(examples) >= 3

    def test_none_path_returns_builtin(self):
        """Verify None path returns built-in examples."""
        examples = load_examples(None)
        builtin = load_builtin_examples()
        assert len(examples) == len(builtin)

    def test_examples_are_valid_format(self):
        """Verify loaded examples can be used in translation."""
        examples = load_examples()
        for ex in examples:
            # Should be usable as few-shot examples
            assert isinstance(ex.get("source"), str)
            assert isinstance(ex.get("target"), str)


class TestExamplesQuality:
    """Tests for example content quality."""

    def test_examples_are_academic(self):
        """Verify examples contain academic language patterns."""
        examples = load_examples()
        # At least one example should have academic patterns
        academic_patterns = [
            "propose",
            "demonstrate",
            "method",
            "approach",
            "result",
            "experiment",
        ]
        found_academic = False
        for ex in examples:
            source_lower = ex["source"].lower()
            if any(pattern in source_lower for pattern in academic_patterns):
                found_academic = True
                break
        assert found_academic, "No academic-style examples found"

    def test_examples_are_translations(self):
        """Verify target is Chinese translation."""
        examples = load_examples()
        for ex in examples:
            # Target should contain Chinese characters
            has_chinese = any("\u4e00" <= char <= "\u9fff" for char in ex["target"])
            assert has_chinese, f"Target not in Chinese: {ex['target'][:50]}"
