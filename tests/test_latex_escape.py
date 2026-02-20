"""
Tests for escape_latex_special_chars() function.

TDD approach: Write failing tests first, then implement.
"""

import pytest
import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ieeA.parser.structure import escape_latex_special_chars


class TestBasicEscaping:
    """Test basic LaTeX special character escaping."""

    def test_percent_escape(self):
        """Basic percent escaping: '50%' -> '50\%'"""
        assert escape_latex_special_chars("50%") == "50\\%"

    def test_ampersand_escape(self):
        """Ampersand escaping: 'A & B' -> 'A \\& B'"""
        assert escape_latex_special_chars("A & B") == "A \\& B"

    def test_hash_escape(self):
        """Hash escaping: '#define' -> '\\#define'"""
        assert escape_latex_special_chars("#define") == "\\#define"


class TestNoDoubleEscape:
    """Test that already escaped characters are not double-escaped."""

    def test_percent_no_double_escape(self):
        """No double-escape: '\\%' stays '\\%'"""
        assert escape_latex_special_chars("\\%") == "\\%"

    def test_ampersand_no_double_escape(self):
        """No double-escape: '\\&' stays '\\&'"""
        assert escape_latex_special_chars("\\&") == "\\&"

    def test_hash_no_double_escape(self):
        """No double-escape: '\\#' stays '\\#'"""
        assert escape_latex_special_chars("\\#") == "\\#"

    def test_mixed_escaped_and_unescaped(self):
        """Mix of escaped and unescaped: '\\% and %' -> '\\% and \\%'"""
        assert escape_latex_special_chars("\\% and %") == "\\% and \\%"


class TestPlaceholderSafety:
    """Test that placeholders are not escaped."""

    def test_double_bracket_placeholder_not_escaped(self):
        """Double bracket placeholder: 'text [[MATH_1]] more%' -> 'text [[MATH_1]] more\\%'"""
        result = escape_latex_special_chars("text [[MATH_1]] more%")
        assert result == "text [[MATH_1]] more\\%"
        assert "[[MATH_1]]" in result

    def test_chunk_placeholder_not_escaped(self):
        """Chunk placeholder: '{{CHUNK_abc123}} %' -> '{{CHUNK_abc123}} \\%'"""
        result = escape_latex_special_chars("{{CHUNK_abc123}} %")
        assert result == "{{CHUNK_abc123}} \\%"
        assert "{{CHUNK_abc123}}" in result

    def test_percent_in_placeholder_not_escaped(self):
        """Placeholder containing percent: '[[MATH_1]]' unchanged"""
        # Placeholders themselves shouldn't be modified even if they contain special chars
        result = escape_latex_special_chars("[[CITE_1]]")
        assert result == "[[CITE_1]]"

    def test_multiple_placeholders(self):
        """Multiple placeholders: 'A% [[MATH_1]] B& [[CITE_2]] C#' preserved"""
        result = escape_latex_special_chars("A% [[MATH_1]] B& [[CITE_2]] C#")
        assert "[[MATH_1]]" in result
        assert "[[CITE_2]]" in result
        assert result == "A\\% [[MATH_1]] B\\& [[CITE_2]] C\\#"

    def test_placeholder_with_uuid_format(self):
        """Chunk placeholder with UUID format"""
        result = escape_latex_special_chars(
            "{{CHUNK_a1b2c3d4-1234-5678-9abc-def012345678}} text%"
        )
        assert "{{CHUNK_a1b2c3d4-1234-5678-9abc-def012345678}}" in result
        assert result.endswith(" text\\%")

    def test_newline_tokens_not_escaped(self):
        """Newline tokens [[SL]], [[PL]], [[SL_RAW]], [[PL_RAW]] should be preserved"""
        result = escape_latex_special_chars("text% [[SL]] more&")
        assert result == "text\\% [[SL]] more\\&"
        result2 = escape_latex_special_chars("text# [[PL]] more%")
        assert result2 == "text\\# [[PL]] more\\%"


class TestMultipleSpecialChars:
    """Test escaping multiple special characters."""

    def test_all_three_special_chars(self):
        """Multiple special chars: 'A & B # C %' -> 'A \\& B \\# C \\%'"""
        result = escape_latex_special_chars("A & B # C %")
        assert result == "A \\& B \\# C \\%"

    def test_consecutive_special_chars(self):
        """Consecutive special chars: '###' -> '\\#\\#\\#'"""
        assert escape_latex_special_chars("###") == "\\#\\#\\#"

    def test_special_chars_with_placeholders(self):
        """Special chars around placeholders"""
        result = escape_latex_special_chars("% [[MATH_1]] & [[CITE_2]] #")
        assert result == "\\% [[MATH_1]] \\& [[CITE_2]] \\#"


class TestEdgeCases:
    """Test edge cases."""

    def test_empty_string(self):
        """Empty string should return empty string"""
        assert escape_latex_special_chars("") == ""

    def test_pure_placeholder_text(self):
        """Pure placeholder text should remain unchanged"""
        assert escape_latex_special_chars("[[MATH_1]]") == "[[MATH_1]]"
        assert escape_latex_special_chars("{{CHUNK_abc123}}") == "{{CHUNK_abc123}}"

    def test_no_special_chars(self):
        """Text without special chars should remain unchanged"""
        text = "Just regular text without special characters"
        assert escape_latex_special_chars(text) == text

    def test_only_escaped_chars(self):
        """Text with only already-escaped chars should remain unchanged"""
        assert escape_latex_special_chars("\\% \\& \\#") == "\\% \\& \\#"

    def test_placeholder_at_start(self):
        """Placeholder at start: '[[MATH_1]] text%'"""
        result = escape_latex_special_chars("[[MATH_1]] text%")
        assert result == "[[MATH_1]] text\\%"

    def test_placeholder_at_end(self):
        """Placeholder at end: 'text% [[MATH_1]]'"""
        result = escape_latex_special_chars("text% [[MATH_1]]")
        assert result == "text\\% [[MATH_1]]"

    def test_adjacent_placeholders(self):
        """Adjacent placeholders: '[[MATH_1]][[CITE_2]] text%'"""
        result = escape_latex_special_chars("[[MATH_1]][[CITE_2]] text%")
        assert result == "[[MATH_1]][[CITE_2]] text\\%"


class TestSpecialCharsNotEscaped:
    """Test that certain special chars are NOT escaped (as per requirements)."""

    def test_underscore_not_escaped(self):
        """Underscore should NOT be escaped"""
        assert escape_latex_special_chars("foo_bar") == "foo_bar"

    def test_dollar_not_escaped(self):
        """Dollar should NOT be escaped"""
        assert escape_latex_special_chars("$100") == "$100"

    def test_backslash_not_escaped_except_for_special_chars(self):
        """Backslash only escapes special chars, not standalone"""
        # Standalone backslash (not before %, &, #) should stay
        assert escape_latex_special_chars("path\\to\\file") == "path\\to\\file"

    def test_braces_not_escaped(self):
        """Braces should NOT be escaped"""
        assert escape_latex_special_chars("{foo}") == "{foo}"

    def test_tilde_not_escaped(self):
        """Tilde should NOT be escaped"""
        assert escape_latex_special_chars("~100") == "~100"

    def test_caret_not_escaped(self):
        """Caret should NOT be escaped"""
        assert escape_latex_special_chars("x^2") == "x^2"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
