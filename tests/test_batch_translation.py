"""Tests for batch translation logic - placeholder skipping and batch processing."""

import pytest
import re
from unittest.mock import AsyncMock, MagicMock, patch
from ieeA.translator.pipeline import TranslationPipeline, TranslatedChunk
from ieeA.translator.prompts import build_batch_translation_text


class TestPlaceholderSkipping:
    """Test pure placeholder detection and skipping logic."""

    def test_is_placeholder_pattern(self):
        """纯占位符正则模式测试"""
        pattern = re.compile(r"^\[\[[A-Z_]+_\d+\]\]$")
        assert pattern.fullmatch("[[AUTHOR_1]]")
        assert pattern.fullmatch("[[MATH_123]]")
        assert pattern.fullmatch("[[CITE_1]]")
        assert not pattern.fullmatch("[[AUTHOR_1]] extra")
        assert not pattern.fullmatch("text [[AUTHOR_1]]")

    def test_placeholder_with_whitespace(self):
        """带空白字符的占位符测试"""
        pattern = re.compile(r"^\[\[[A-Z_]+_\d+\]\]$")
        # strip() 后应匹配
        text = "  [[MATH_1]]  "
        assert pattern.fullmatch(text.strip())

    def test_multiple_placeholders_not_match(self):
        """多个占位符不应匹配纯占位符模式"""
        pattern = re.compile(r"^\[\[[A-Z_]+_\d+\]\]$")
        assert not pattern.fullmatch("[[MATH_1]] [[CITE_2]]")

    def test_placeholder_types(self):
        """各种类型的占位符"""
        pattern = re.compile(r"^\[\[[A-Z_]+_\d+\]\]$")
        placeholders = [
            "[[CITE_1]]",
            "[[REF_2]]",
            "[[MATH_3]]",
            "[[ENV_4]]",
            "[[GRAPHICS_5]]",
            "[[LABEL_6]]",
            "[[FOOTNOTE_7]]",
            "[[AUTHOR_8]]",
        ]
        for ph in placeholders:
            assert pattern.fullmatch(ph), f"{ph} should match"


class TestBatchTranslation:
    """Test batch translation text formatting and response parsing."""

    def test_batch_text_format(self):
        """批量文本格式测试"""
        chunks = [
            {"chunk_id": "1", "content": "Introduction"},
            {"chunk_id": "2", "content": "Methods"},
        ]
        result = build_batch_translation_text(chunks)
        assert "[1] Introduction" in result
        assert "[2] Methods" in result

    def test_batch_response_parsing(self):
        """批量响应解析测试"""
        response = "[1] 引言\n[2] 方法\n[3] 结果"
        pattern = r"\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)"
        matches = re.findall(pattern, response, re.DOTALL)
        assert len(matches) == 3
        assert matches[0] == ("1", "引言\n")
        assert matches[1] == ("2", "方法\n")
        assert matches[2] == ("3", "结果")

    def test_batch_text_format_with_multiple_chunks(self):
        """多个chunk的批量格式测试"""
        chunks = [
            {"chunk_id": "c1", "content": "First paragraph"},
            {"chunk_id": "c2", "content": "Second paragraph"},
            {"chunk_id": "c3", "content": "Third paragraph"},
        ]
        result = build_batch_translation_text(chunks)
        assert "[1] First paragraph" in result
        assert "[2] Second paragraph" in result
        assert "[3] Third paragraph" in result

    def test_batch_response_parsing_multiline(self):
        """多行响应解析测试"""
        response = """[1] 这是第一段
内容继续

[2] 这是第二段
也有多行

[3] 第三段"""
        pattern = r"\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)"
        matches = re.findall(pattern, response, re.DOTALL)
        assert len(matches) == 3
        assert "第一段" in matches[0][1]
        assert "第二段" in matches[1][1]
        assert "第三段" in matches[2][1]

    def test_batch_response_parsing_with_placeholders(self):
        """包含占位符的批量响应解析"""
        response = "[1] 参考[[CITE_1]]显示\n[2] 公式[[MATH_1]]表明"
        pattern = r"\[(\d+)\]\s*(.+?)(?=\[\d+\]|$)"
        matches = re.findall(pattern, response, re.DOTALL)
        assert len(matches) == 2
        assert "[[CITE_1]]" in matches[0][1]
        assert "[[MATH_1]]" in matches[1][1]

    def test_empty_batch(self):
        """空批量测试"""
        chunks = []
        result = build_batch_translation_text(chunks)
        assert result == ""

    def test_single_chunk_batch(self):
        """单个chunk的批量测试"""
        chunks = [{"chunk_id": "1", "content": "Only one"}]
        result = build_batch_translation_text(chunks)
        assert "[1] Only one" in result


class TestBatchTranslationIntegration:
    """Integration tests for batch translation with mocked LLM."""

    @pytest.mark.asyncio
    async def test_placeholder_chunks_skipped(self):
        """纯占位符chunks应被跳过不调用LLM"""
        mock_provider = AsyncMock()
        mock_provider.translate = AsyncMock(return_value="翻译结果")

        pipeline = TranslationPipeline(provider=mock_provider)

        chunks = [
            {"chunk_id": "1", "content": "[[MATH_1]]"},
            {"chunk_id": "2", "content": "Real text to translate"},
            {"chunk_id": "3", "content": "[[CITE_2]]"},
        ]

        # Mock translate_chunk for real content
        async def mock_translate_chunk(chunk, chunk_id, context=None):
            return TranslatedChunk(
                source=chunk,
                translation="翻译: " + chunk,
                chunk_id=chunk_id,
                metadata={},
            )

        with patch.object(
            pipeline, "translate_chunk", side_effect=mock_translate_chunk
        ):
            results = await pipeline.translate_document(chunks, max_concurrent=1)

        assert len(results) == 3
        # 占位符应直接返回原文
        assert results[0].translation == "[[MATH_1]]"
        assert results[0].metadata.get("skipped_placeholder") is True
        # 真实内容应被翻译
        assert "翻译:" in results[1].translation
        # 第三个占位符
        assert results[2].translation == "[[CITE_2]]"
        assert results[2].metadata.get("skipped_placeholder") is True

    @pytest.mark.asyncio
    async def test_batch_fallback_on_parse_failure(self):
        """批量翻译解析失败时应回退到单独翻译"""
        mock_provider = AsyncMock()

        # Mock translate to return malformed batch response
        async def mock_translate(
            text,
            context=None,
            glossary_hints=None,
            few_shot_examples=None,
            custom_system_prompt=None,
        ):
            if "[1]" in text and "[2]" in text:
                # 返回格式错误的响应
                return "格式错误的响应"
            else:
                # 单独翻译正常工作
                return "翻译: " + text

        mock_provider.translate = mock_translate

        pipeline = TranslationPipeline(provider=mock_provider)

        chunks = [
            {"chunk_id": "1", "content": "Short 1"},
            {"chunk_id": "2", "content": "Short 2"},
        ]

        results = await pipeline.translate_document(chunks, max_concurrent=1)

        # 应该回退到单独翻译
        assert len(results) == 2
        assert "翻译:" in results[0].translation
        assert "翻译:" in results[1].translation
