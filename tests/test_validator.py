import pytest
from ieet.validator.engine import ValidationEngine
from ieet.validator.rules import BuiltInRules
from ieet.rules.validation_rules import ValidationRule, RuleSet

class TestValidationEngine:
    @pytest.fixture
    def engine(self):
        return ValidationEngine()

    def test_validate_braces_balanced(self, engine):
        original = r"Some text \textbf{bold}."
        translated = r"一些文本 \textbf{bold}."
        result = engine.validate(translated, original)
        assert result.valid
        assert len(result.errors) == 0

    def test_validate_braces_unbalanced(self, engine):
        original = r"Some text."
        translated = r"一些文本 \textbf{bold."
        result = engine.validate(translated, original)
        assert not result.valid
        assert any("Unbalanced braces" in e.message for e in result.errors)

    def test_validate_citations_preserved(self, engine):
        original = r"See \cite{ref1}."
        translated = r"见 \cite{ref1}。"
        result = engine.validate(translated, original)
        assert result.valid

    def test_validate_citations_missing(self, engine):
        original = r"See \cite{ref1} and \cite{ref2}."
        translated = r"见 \cite{ref1} 和引用。"
        result = engine.validate(translated, original)
        assert not result.valid
        assert any("Missing citation" in e.message for e in result.errors)

    def test_validate_citations_altered(self, engine):
        original = r"See \cite{ref1}."
        translated = r"见 \cite{ref2}。"
        result = engine.validate(translated, original)
        assert not result.valid
        assert any("Unexpected citation" in e.message for e in result.errors)

    def test_math_env_preserved(self, engine):
        original = r"Equation $E=mc^2$."
        translated = r"方程 $E=mc^2$。"
        result = engine.validate(translated, original)
        assert result.valid

    def test_math_env_corrupted(self, engine):
        original = r"Equation $E=mc^2$."
        translated = r"方程 $E=mc^2（去掉了结束符"
        result = engine.validate(translated, original)
        # This might be caught by brace/syntax check or specific math check
        # For simplicity, we assume math check catches specific delimiter issues
        assert not result.valid

    def test_glossary_compliance(self, engine):
        # We need to inject a glossary context or mock it
        # Assuming engine accepts a glossary or uses a global one.
        # For this test, we might need to mock the glossary loader or pass it.
        # Let's assume validate accepts an optional glossary or rules.
        pass # To be implemented when glossary integration is clear

    def test_apply_fixes(self, engine):
        translated = "Some bad pattern."
        rules = RuleSet(rules=[
            ValidationRule(
                id="fix1",
                description="Fix bad pattern",
                pattern="bad pattern",
                replacement="good pattern",
                severity="warning"
            )
        ])
        fixed = engine.apply_fixes(translated, rules)
        assert fixed == "Some good pattern."

    def test_length_ratio_check(self, engine):
        original = "Short."
        translated = "Very very very very very very very long translation that is clearly too verbose."
        # Ratio: len(trans)/len(orig) >> 0.8 (assuming char count or similar)
        result = engine.validate(translated, original)
        # This is a soft check (warning), so valid might still be True depending on strictness
        # or we check warnings.
        assert any("Length ratio" in e.message for e in result.errors if e.severity == "warning")

