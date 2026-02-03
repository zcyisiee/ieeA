"""Tests for validator fixes - brace checking and math environment validation."""

import pytest
from ieeA.validator.rules import BuiltInRules


class TestCheckBraces:
    """Test brace checking with escaped braces and parentheses handling."""

    def test_escaped_braces_not_reported(self):
        """转义括号不应报告为不匹配"""
        result = BuiltInRules.check_braces(r"Text with \{ escaped \} braces")
        assert result == []

    def test_parentheses_ignored(self):
        """圆括号应被忽略"""
        result = BuiltInRules.check_braces("Text with (parentheses) and unbalanced {")
        # 应该只报告 { 的错误，不报告 ( 的错误
        assert len(result) == 1
        assert "{" in result[0]
        assert "(" not in result[0]

    def test_balanced_braces_pass(self):
        """平衡的括号应通过"""
        result = BuiltInRules.check_braces("{hello} [world]")
        assert result == []

    def test_left_right_braces_handled(self):
        r"""\\left\\{ 和 \\right\\} 应被正确处理"""
        result = BuiltInRules.check_braces(r"Math \left\{ x \right\}")
        assert result == []

    def test_multiple_escaped_braces(self):
        """多个转义括号应被正确处理"""
        result = BuiltInRules.check_braces(r"\{ first \} and \{ second \}")
        assert result == []

    def test_mixed_escaped_and_normal(self):
        """混合转义和普通括号"""
        result = BuiltInRules.check_braces(r"\{ escaped \} {normal}")
        assert result == []

    def test_unbalanced_after_escaped(self):
        """转义后仍有不平衡括号"""
        result = BuiltInRules.check_braces(r"\{ escaped \} {unbalanced")
        assert len(result) == 1
        assert "Unmatched" in result[0]


class TestCheckMathEnvironments:
    """Test math environment validation with placeholder exclusion."""

    def test_placeholder_excluded(self):
        """占位符区域应被排除"""
        orig = "Before [[MATH_1]] after"
        trans = "Before [[MATH_1]] after"
        result = BuiltInRules.check_math_environments(orig, trans)
        assert result == []

    def test_escaped_dollar_ignored(self):
        r"""转义的 \\$ 应被忽略"""
        orig = r"Cost is \$100"
        trans = r"Cost is \$100"
        result = BuiltInRules.check_math_environments(orig, trans)
        assert result == []

    def test_real_mismatch_detected(self):
        """真正的不匹配应被检测到"""
        orig = "$x$ and $y$"
        trans = "$x$ and y"
        result = BuiltInRules.check_math_environments(orig, trans)
        assert len(result) > 0
        assert "mismatch" in result[0].lower()

    def test_multiple_placeholders(self):
        """多个占位符应被正确排除"""
        orig = "[[MATH_1]] and [[MATH_2]] text"
        trans = "[[MATH_1]] and [[MATH_2]] 文本"
        result = BuiltInRules.check_math_environments(orig, trans)
        assert result == []

    def test_escaped_dollar_with_real_math(self):
        """转义美元符号和真实数学公式混合"""
        orig = r"Price \$50 and formula $x=1$"
        trans = r"价格 \$50 和公式 $x=1$"
        result = BuiltInRules.check_math_environments(orig, trans)
        assert result == []

    def test_odd_dollar_signs(self):
        """奇数个美元符号应被检测"""
        orig = "$x$ and $y$"
        trans = "$x$ and $y"
        result = BuiltInRules.check_math_environments(orig, trans)
        assert len(result) > 0
        assert "Odd number" in result[0]

    def test_placeholder_with_math(self):
        """占位符和数学公式混合"""
        orig = "[[CITE_1]] shows $E=mc^2$"
        trans = "[[CITE_1]] 显示 $E=mc^2$"
        result = BuiltInRules.check_math_environments(orig, trans)
        assert result == []
