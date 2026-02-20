"""Tests for timeout handling and graceful skip functionality."""

import asyncio
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from ieeA.translator.pipeline import TranslationPipeline, TranslatedChunk


class TestGracefulSkipOnTimeout:
    """Test that timeout errors result in graceful skip with original text preserved."""

    @pytest.mark.asyncio
    async def test_translate_chunk_timeout_returns_original_text(self):
        """当 translate_chunk 超时时，应返回原文而不是崩溃。"""
        mock_provider = AsyncMock()
        mock_provider.translate = AsyncMock(
            side_effect=TimeoutError("Request timed out after 120.0s")
        )

        pipeline = TranslationPipeline(
            provider=mock_provider, max_retries=1, per_call_timeout=1.0
        )

        chunks = [
            {"chunk_id": "chunk_1", "content": "Original English text to preserve"},
        ]

        results = await pipeline.translate_document(chunks, max_concurrent=1)

        assert len(results) == 1
        # 超时的 chunk 应保留原文
        assert results[0].translation == "Original English text to preserve"
        assert results[0].source == "Original English text to preserve"
        # 元数据应标记为跳过
        assert results[0].metadata.get("skipped") is True
        assert "timed out" in results[0].metadata.get("skip_reason", "").lower()
        assert "skipped_at" in results[0].metadata

    @pytest.mark.asyncio
    async def test_partial_timeout_some_chunks_succeed(self):
        """部分 chunk 超时，其他应正常翻译。"""
        mock_provider = AsyncMock()

        call_count = 0

        async def mock_translate(
            text,
            context=None,
            glossary_hints=None,
            few_shot_examples=None,
            custom_system_prompt=None,
        ):
            nonlocal call_count
            call_count += 1
            if "timeout" in text.lower():
                raise TimeoutError("Request timed out after 120.0s")
            return f"翻译: {text}"

        mock_provider.translate = mock_translate

        pipeline = TranslationPipeline(provider=mock_provider, max_retries=1)

        chunks = [
            {"chunk_id": "chunk_1", "content": "Normal text"},
            {"chunk_id": "chunk_2", "content": "This will timeout"},
            {"chunk_id": "chunk_3", "content": "Another normal"},
        ]

        results = await pipeline.translate_document(chunks, max_concurrent=1)

        assert len(results) == 3
        # chunk_1 和 chunk_3 应正常翻译
        assert "翻译:" in results[0].translation
        assert "翻译:" in results[2].translation
        # chunk_2 应保留原文
        assert results[1].translation == "This will timeout"
        assert results[1].metadata.get("skipped") is True

    @pytest.mark.asyncio
    async def test_batch_fallback_timeout_graceful_skip(self):
        """批量翻译失败后，单个 chunk 重试超时时应优雅跳过。"""
        mock_provider = AsyncMock()
        mock_provider.translate = AsyncMock(
            side_effect=TimeoutError("Request timed out after 120.0s (attempt 5/5)")
        )

        pipeline = TranslationPipeline(provider=mock_provider, max_retries=1)

        # 使用短内容触发 batch 路径
        chunks = [
            {"chunk_id": "c1", "content": "Short"},
            {"chunk_id": "c2", "content": "Text"},
        ]

        results = await pipeline.translate_document(chunks, max_concurrent=1)

        assert len(results) == 2
        # 所有 chunk 都应保留原文
        assert results[0].translation == "Short"
        assert results[1].translation == "Text"
        assert results[0].metadata.get("skipped") is True
        assert results[1].metadata.get("skipped") is True


class TestSemaphoreRelease:
    """Test that semaphore is released before fallback to allow concurrency."""

    @pytest.mark.asyncio
    async def test_semaphore_released_before_fallback(self):
        """验证 batch 失败后 semaphore 被释放，fallback chunks 可以并发执行。"""
        mock_provider = AsyncMock()

        # 记录每个 chunk 开始翻译的时间
        start_times = {}

        async def mock_translate(
            text,
            context=None,
            glossary_hints=None,
            few_shot_examples=None,
            custom_system_prompt=None,
        ):
            import time

            # 使用 chunk_id 作为 key（从 text 推断）
            chunk_id = None
            for c in ["chunk_1", "chunk_2", "chunk_3"]:
                if c.replace("_", "") in text.lower() or c in text:
                    chunk_id = c
                    break
            if chunk_id is None:
                chunk_id = f"unknown_{time.time()}"

            start_times[chunk_id] = time.time()
            # 模拟短暂处理时间
            await asyncio.sleep(0.1)
            return f"翻译: {text}"

        mock_provider.translate = mock_translate

        # semaphore=1，如果 semaphore 不释放，chunks 会串行执行
        pipeline = TranslationPipeline(provider=mock_provider, max_retries=1)

        # 使用较长的内容触发 batch 路径（然后 batch 会失败并 fallback）
        chunks = [
            {
                "chunk_id": "chunk_1",
                "content": "This is a longer text that should be batched but will fail and fallback",
            },
            {
                "chunk_id": "chunk_2",
                "content": "Another longer text for testing concurrent fallback execution",
            },
        ]

        # patch translate_batch to always fail, forcing fallback
        with patch.object(pipeline, "translate_batch", return_value=[]):
            results = await pipeline.translate_document(chunks, max_concurrent=2)

        assert len(results) == 2
        # 两个 chunk 都应该被翻译（不是跳过）
        assert "翻译:" in results[0].translation
        assert "翻译:" in results[1].translation

    @pytest.mark.asyncio
    async def test_concurrent_fallback_chunks(self):
        """验证多个 batch 同时 fallback 时可以并发执行。"""
        mock_provider = AsyncMock()

        active_count = 0
        max_active = 0

        async def mock_translate(
            text,
            context=None,
            glossary_hints=None,
            few_shot_examples=None,
            custom_system_prompt=None,
        ):
            nonlocal active_count, max_active

            active_count += 1
            max_active = max(max_active, active_count)
            await asyncio.sleep(0.05)  # 短暂延迟
            active_count -= 1

            return f"翻译: {text}"

        mock_provider.translate = mock_translate

        pipeline = TranslationPipeline(provider=mock_provider, max_retries=1)

        # 创建多个 batch，每个 batch 包含多个 chunks
        chunks = [
            {
                "chunk_id": f"c{i}",
                "content": f"Text content for chunk {i} that is long enough",
            }
            for i in range(4)
        ]

        # patch translate_batch to fail for all batches
        with patch.object(pipeline, "translate_batch", return_value=[]):
            results = await pipeline.translate_document(chunks, max_concurrent=4)

        assert len(results) == 4
        # 验证有并发执行（max_active > 1）
        assert max_active > 1, (
            f"Expected concurrent execution, but max_active was {max_active}"
        )


class TestPerCallTimeout:
    """Test per-attempt wall-clock timeout functionality."""

    @pytest.mark.asyncio
    async def test_per_call_timeout_interrupts_slow_requests(self):
        """验证 asyncio.wait_for 在 per_call_timeout 后中断慢请求。"""
        mock_provider = AsyncMock()

        async def slow_translate(*args, **kwargs):
            await asyncio.sleep(999)  # 非常慢的请求
            return "翻译结果"

        mock_provider.translate = slow_translate

        # 设置很短的 per_call_timeout
        pipeline = TranslationPipeline(
            provider=mock_provider, max_retries=1, per_call_timeout=0.1
        )

        chunks = [{"chunk_id": "c1", "content": "Test"}]

        start = asyncio.get_event_loop().time()
        results = await pipeline.translate_document(chunks, max_concurrent=1)
        elapsed = asyncio.get_event_loop().time() - start

        # 应该在约 0.1s 后超时，而不是等待 999s
        assert elapsed < 1.0, f"Expected < 1s, but took {elapsed}s"
        # chunk 应被跳过，保留原文
        assert results[0].translation == "Test"
        assert results[0].metadata.get("skipped") is True

    @pytest.mark.asyncio
    async def test_timeout_error_recognized_in_retry(self):
        """验证 timeout 错误在 retry 逻辑中被正确识别。"""
        mock_provider = AsyncMock()

        error_messages = [
            "Request timed out after 120.0s",
            "connection timeout",
            "operation timed out",
        ]
        call_count = 0

        async def failing_translate(*args, **kwargs):
            nonlocal call_count
            msg = error_messages[min(call_count, len(error_messages) - 1)]
            call_count += 1
            raise TimeoutError(msg)

        mock_provider.translate = failing_translate

        pipeline = TranslationPipeline(
            provider=mock_provider, max_retries=2, retry_delay=0.01
        )

        # Use a long chunk to bypass batch processing and test _call_with_retry directly
        chunks = [
            {
                "chunk_id": "c1",
                "content": "This is a long text that will not be batched",
            }
        ]

        results = await pipeline.translate_document(chunks, max_concurrent=1)

        # 应该重试 max_retries 次 (attempt 0 and 1)
        assert call_count >= 2, f"Expected at least 2 calls, got {call_count}"
        assert results[0].metadata.get("skipped") is True


class TestTimeoutErrorDetection:
    """Test timeout error detection in _call_with_retry."""

    @pytest.mark.asyncio
    async def test_string_timeout_error_detection(self):
        """验证通过字符串匹配的 timeout 错误检测。"""
        mock_provider = AsyncMock()

        # 模拟 DashScope 风格的 timeout 错误消息
        async def timeout_translate(*args, **kwargs):
            raise Exception("Request timed out after 120.0s (attempt 3/5)")

        mock_provider.translate = timeout_translate

        pipeline = TranslationPipeline(
            provider=mock_provider, max_retries=1, retry_delay=0.01
        )

        # 调用 _call_with_retry 应该能识别 timeout 错误
        with pytest.raises(Exception) as exc_info:
            await pipeline._call_with_retry("test text")

        assert "timed out" in str(exc_info.value).lower()


class TestStateFileSkippedRecording:
    """Test that skipped chunks are recorded in state file."""

    @pytest.mark.asyncio
    async def test_skipped_chunk_metadata_format(self):
        """验证跳过的 chunk 的 metadata 格式正确且可序列化。"""
        mock_provider = AsyncMock()

        async def failing_translate(*args, **kwargs):
            raise TimeoutError("Request timed out after 120.0s")

        mock_provider.translate = failing_translate

        pipeline = TranslationPipeline(
            provider=mock_provider,
            max_retries=1,
        )

        chunks = [
            {"chunk_id": "chunk_timeout", "content": "Will timeout"},
        ]

        results = await pipeline.translate_document(chunks, max_concurrent=1)

        # 验证结果格式正确
        assert len(results) == 1
        assert results[0].chunk_id == "chunk_timeout"
        assert results[0].translation == "Will timeout"
        assert results[0].metadata.get("skipped") is True
        assert "timed out" in results[0].metadata.get("skip_reason", "").lower()
        assert "skipped_at" in results[0].metadata

        # 验证 metadata 可以 JSON 序列化
        import json

        metadata_json = json.dumps(results[0].metadata)
        assert "skipped" in metadata_json
