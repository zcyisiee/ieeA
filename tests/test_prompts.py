"""Tests for prompt building functions."""

import pytest
from ieeA.translator.prompts import (
    CORE_TRANSLATION_RULES,
    TRANSLATION_SYSTEM_PROMPT,
    build_system_prompt,
    build_translation_prompt,
    build_system_message,
)


class TestCoreTranslationRules:
    """Tests for CORE_TRANSLATION_RULES constant."""

    def test_rules_exist(self):
        """Verify CORE_TRANSLATION_RULES is defined."""
        assert CORE_TRANSLATION_RULES
        assert len(CORE_TRANSLATION_RULES) > 100

    def test_rules_contain_key_instructions(self):
        """Verify rules contain key translation instructions."""
        assert "改写" in CORE_TRANSLATION_RULES
        assert "占位符" in CORE_TRANSLATION_RULES
        assert "LaTeX" in CORE_TRANSLATION_RULES
        assert "核心规则" in CORE_TRANSLATION_RULES


class TestBuildSystemPrompt:
    """Tests for build_system_prompt function."""

    def test_basic_prompt(self):
        """Verify basic prompt contains core rules."""
        prompt = build_system_prompt()
        assert "核心规则" in prompt
        assert "LaTeX" in prompt

    def test_with_context(self):
        """Verify context is included in prompt."""
        prompt = build_system_prompt(context="This is the paper abstract.")
        assert "上下文" in prompt
        assert "This is the paper abstract." in prompt

    def test_with_glossary(self):
        """Verify glossary hints are included."""
        prompt = build_system_prompt(glossary_hints={"Transformer": "变换器"})
        assert "术语表" in prompt
        assert "Transformer" in prompt
        assert "变换器" in prompt

    def test_with_context_and_glossary(self):
        """Verify both context and glossary are included."""
        prompt = build_system_prompt(
            context="Test context",
            glossary_hints={"term": "术语"},
        )
        assert "上下文" in prompt
        assert "Test context" in prompt
        assert "术语表" in prompt
        assert "term" in prompt


class TestBuildTranslationPrompt:
    """Tests for build_translation_prompt function (backward compatibility)."""

    def test_basic_prompt(self):
        """Verify basic translation prompt is built."""
        prompt = build_translation_prompt("Hello world")
        assert "Hello world" in prompt
        assert "待翻译文本" in prompt

    def test_with_context(self):
        """Verify context is included."""
        prompt = build_translation_prompt("Test", context="Academic context")
        assert "Academic context" in prompt

    def test_with_glossary_hints(self):
        """Verify glossary hints are included."""
        prompt = build_translation_prompt(
            "Test",
            glossary_hints={"term1": "术语1", "term2": "术语2"},
        )
        assert "term1" in prompt
        assert "术语1" in prompt

    def test_with_few_shot_examples(self):
        """Verify few-shot examples are included."""
        prompt = build_translation_prompt(
            "Test",
            few_shot_examples=[
                {"source": "Hello", "target": "你好"},
                {"source": "World", "target": "世界"},
            ],
        )
        assert "示例" in prompt
        assert "Hello" in prompt
        assert "你好" in prompt


class TestBuildSystemMessage:
    """Tests for build_system_message function (backward compatibility)."""

    def test_basic_message(self):
        """Verify basic system message is built."""
        message = build_system_message()
        assert "翻译" in message

    def test_with_glossary(self):
        """Verify glossary is included in message."""
        message = build_system_message(glossary_hints={"key": "值"})
        assert "key" in message
        assert "值" in message

    def test_with_custom_prompt(self):
        """Verify custom prompt overrides default."""
        custom = "Custom system prompt"
        message = build_system_message(custom_system_prompt=custom)
        assert custom in message
