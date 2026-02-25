"""Tests for provider cache mechanisms."""

import asyncio
import time
import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestOpenAIProviderCache:
    """Test OpenAIProvider pre-built prompt bypass."""

    async def test_bypass_uses_prebuilt_prompt(self):
        """When _prebuilt_system_prompt is set, it should be used directly."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.openai_provider import OpenAIProvider

            provider = OpenAIProvider(model="test", api_key="test")
            provider._prebuilt_system_prompt = "FIXED_PROMPT"

            result = await provider.translate("test text", glossary_hints=None)

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])
            assert messages[0]["content"] == "FIXED_PROMPT"

    async def test_fallback_without_prebuilt(self):
        """When _prebuilt_system_prompt is None, should use build_system_prompt."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.openai_provider import OpenAIProvider

            provider = OpenAIProvider(model="test", api_key="test")

            result = await provider.translate("test", glossary_hints={"AI": "AI"})

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])
            assert "AI" in messages[0]["content"]

    async def test_prebuilt_ignored_when_glossary_hints_provided(self):
        """When glossary_hints is provided, prebuilt prompt should NOT be used."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.openai_provider import OpenAIProvider

            provider = OpenAIProvider(model="test", api_key="test")
            provider._prebuilt_system_prompt = "FIXED_PROMPT"

            result = await provider.translate("test", glossary_hints={"NLP": "NLP"})

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])
            # Should NOT be the prebuilt prompt — should be dynamically built
            assert messages[0]["content"] != "FIXED_PROMPT"
            assert "NLP" in messages[0]["content"]


class TestAnthropicProviderCache:
    """Test AnthropicProvider system blocks + cache_control."""

    async def test_system_blocks_format(self):
        """When prebuilt prompt is set, system should be a list with cache_control."""
        with patch("ieeA.translator.anthropic_provider.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic = MagicMock
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_block = MagicMock()
            mock_block.type = "text"
            mock_block.text = "translated"
            mock_response.content = [mock_block]
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            from ieeA.translator.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider.__new__(AnthropicProvider)
            provider.model = "claude-3-5-sonnet"
            provider.api_key = "test"
            provider.kwargs = {"max_tokens": 4096, "temperature": 0.3}
            provider.client = mock_client
            provider._prebuilt_system_prompt = "FIXED_PROMPT"
            provider._prebuilt_batch_prompt = None

            result = await provider.translate("test", glossary_hints=None)

            call_args = mock_client.messages.create.call_args
            system_arg = call_args.kwargs.get("system")
            assert isinstance(system_arg, list)
            assert system_arg[-1]["cache_control"] == {"type": "ephemeral"}
            assert system_arg[-1]["text"] == "FIXED_PROMPT"

    async def test_fallback_to_string(self):
        """When no prebuilt prompt, system should be a string."""
        with patch("ieeA.translator.anthropic_provider.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic = MagicMock
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_block = MagicMock()
            mock_block.type = "text"
            mock_block.text = "translated"
            mock_response.content = [mock_block]
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            from ieeA.translator.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider.__new__(AnthropicProvider)
            provider.model = "claude-3-5-sonnet"
            provider.api_key = "test"
            provider.kwargs = {"max_tokens": 4096, "temperature": 0.3}
            provider.client = mock_client
            provider._prebuilt_system_prompt = None
            provider._prebuilt_batch_prompt = None

            result = await provider.translate("test", glossary_hints={"AI": "AI"})

            call_args = mock_client.messages.create.call_args
            system_arg = call_args.kwargs.get("system")
            assert isinstance(system_arg, str)
            assert "AI" in system_arg

    async def test_cache_control_structure(self):
        """Cache control should have exactly the right structure."""
        with patch("ieeA.translator.anthropic_provider.anthropic") as mock_anthropic:
            mock_anthropic.AsyncAnthropic = MagicMock
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_block = MagicMock()
            mock_block.type = "text"
            mock_block.text = "translated"
            mock_response.content = [mock_block]
            mock_client.messages.create = AsyncMock(return_value=mock_response)

            from ieeA.translator.anthropic_provider import AnthropicProvider

            provider = AnthropicProvider.__new__(AnthropicProvider)
            provider.model = "claude-3-5-sonnet"
            provider.api_key = "test"
            provider.kwargs = {"max_tokens": 4096, "temperature": 0.3}
            provider.client = mock_client
            provider._prebuilt_system_prompt = "CACHED_PROMPT"
            provider._prebuilt_batch_prompt = None

            await provider.translate("test", glossary_hints=None)

            call_args = mock_client.messages.create.call_args
            system_arg = call_args.kwargs.get("system")
            assert len(system_arg) == 1
            block = system_arg[0]
            assert block["type"] == "text"
            assert block["text"] == "CACHED_PROMPT"
            assert "cache_control" in block


class TestHTTPProviderCache:
    """Test DirectHTTPProvider pre-built prompt bypass."""

    async def test_bypass_uses_prebuilt_prompt(self):
        """When _prebuilt_system_prompt is set, it should be used directly."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "translated"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("ieeA.translator.http_provider.httpx.AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.return_value = mock_client

            from ieeA.translator.http_provider import DirectHTTPProvider

            provider = DirectHTTPProvider(
                model="test",
                api_key="test",
                endpoint="http://test/v1/chat/completions",
            )
            provider._prebuilt_system_prompt = "FIXED_PROMPT"

            result = await provider.translate("test text", glossary_hints=None)

            call_args = mock_client.post.call_args
            request_body = call_args.kwargs.get("json", {})
            assert request_body["messages"][0]["content"] == "FIXED_PROMPT"

    async def test_fallback_without_prebuilt(self):
        """When _prebuilt_system_prompt is None, should use build_system_prompt."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "translated"}}]
        }
        mock_response.raise_for_status = MagicMock()

        with patch("ieeA.translator.http_provider.httpx.AsyncClient") as mock_httpx:
            mock_client = MagicMock()
            mock_client.post = AsyncMock(return_value=mock_response)
            mock_httpx.return_value = mock_client

            from ieeA.translator.http_provider import DirectHTTPProvider

            provider = DirectHTTPProvider(
                model="test",
                api_key="test",
                endpoint="http://test/v1/chat/completions",
            )

            result = await provider.translate("test", glossary_hints={"AI": "AI"})

            call_args = mock_client.post.call_args
            request_body = call_args.kwargs.get("json", {})
            assert "AI" in request_body["messages"][0]["content"]


class TestArkProviderCache:
    """Test ArkProvider structure and interface."""

    def test_ark_provider_extends_llmprovider(self):
        """ArkProvider should be a subclass of LLMProvider."""
        from ieeA.translator.ark_provider import ArkProvider
        from ieeA.translator.llm_base import LLMProvider

        assert issubclass(ArkProvider, LLMProvider)

    def test_ark_provider_has_required_methods(self):
        """ArkProvider should have all required methods."""
        from ieeA.translator.ark_provider import ArkProvider

        assert hasattr(ArkProvider, "translate")
        assert hasattr(ArkProvider, "ping")
        assert hasattr(ArkProvider, "estimate_tokens")
        assert hasattr(ArkProvider, "setup_context")

    def test_ark_import_error_without_sdk(self):
        """ArkProvider should raise ImportError when SDK is not installed."""
        from ieeA.translator.ark_provider import HAS_ARK

        if not HAS_ARK:
            from ieeA.translator.ark_provider import ArkProvider

            with pytest.raises(ImportError, match="volcenginesdkarkruntime"):
                ArkProvider(model="test")

    def test_ark_provider_has_prebuilt_attributes(self):
        """ArkProvider class should support prebuilt prompt attributes."""
        from ieeA.translator.ark_provider import ArkProvider

        # Check via __init__ source or class definition that attributes are initialized
        import inspect

        source = inspect.getsource(ArkProvider.__init__)
        assert "_prebuilt_system_prompt" in source
        assert "_prebuilt_batch_prompt" in source

    def test_ark_provider_uses_async_client(self):
        """ArkProvider must use AsyncArk, not sync Ark."""
        import inspect
        from ieeA.translator.ark_provider import ArkProvider

        source = inspect.getsource(ArkProvider)
        # Must NOT contain sync Ark import/usage
        assert "from volcenginesdkarkruntime import Ark " not in source
        # Module-level import should be AsyncArk
        import ieeA.translator.ark_provider as ark_mod

        module_source = inspect.getsource(ark_mod)
        assert "AsyncArk" in module_source
        assert "import Ark as _ArkClass" not in module_source

    def test_ark_translate_is_truly_async(self):
        """ArkProvider.translate must be a coroutine function."""
        import asyncio
        from ieeA.translator.ark_provider import ArkProvider

        assert asyncio.iscoroutinefunction(ArkProvider.translate)

    def test_ark_setup_context_is_async(self):
        """ArkProvider.setup_context must be a coroutine function."""
        import asyncio
        from ieeA.translator.ark_provider import ArkProvider

        assert asyncio.iscoroutinefunction(ArkProvider.setup_context)

    def test_ark_ping_is_async(self):
        """ArkProvider.ping must be a coroutine function."""
        import asyncio
        from ieeA.translator.ark_provider import ArkProvider

        assert asyncio.iscoroutinefunction(ArkProvider.ping)

    def test_ark_all_sdk_calls_use_await(self):
        """Every self.client.* call in ArkProvider must be awaited."""
        import ast
        import inspect
        from ieeA.translator.ark_provider import ArkProvider

        source = inspect.getsource(ArkProvider)
        tree = ast.parse(source)

        # Find all calls to self.client.* and verify they are wrapped in Await
        class AwaitChecker(ast.NodeVisitor):
            def __init__(self):
                self.unawaited_calls = []
                self._in_await = False

            def visit_Await(self, node):
                old = self._in_await
                self._in_await = True
                self.generic_visit(node)
                self._in_await = old

            def visit_Call(self, node):
                # Check if this is a self.client.* call
                if self._is_client_call(node.func):
                    if not self._in_await:
                        self.unawaited_calls.append(ast.dump(node.func))
                self.generic_visit(node)

            def _is_client_call(self, node):
                """Check if node is self.client.something.something(...)"""
                parts = []
                current = node
                while isinstance(current, ast.Attribute):
                    parts.append(current.attr)
                    current = current.value
                if isinstance(current, ast.Attribute) and current.attr == "client":
                    if (
                        isinstance(current.value, ast.Name)
                        and current.value.id == "self"
                    ):
                        return True
                return False

        checker = AwaitChecker()
        checker.visit(tree)
        assert checker.unawaited_calls == [], (
            f"Found unawaited self.client.* calls: {checker.unawaited_calls}"
        )

    async def test_ark_concurrent_translate_not_serialized(self):
        """Multiple ArkProvider.translate calls via gather should run concurrently."""
        from ieeA.translator.ark_provider import ArkProvider, HAS_ARK

        if not HAS_ARK:
            pytest.skip("volcenginesdkarkruntime not installed")

        # Create provider with mocked async client
        provider = ArkProvider.__new__(ArkProvider)
        provider.model = "test-model"
        provider.api_key = "test"
        provider.kwargs = {"temperature": 0.3}
        provider._prebuilt_system_prompt = None
        provider._prebuilt_batch_prompt = None
        provider._context_id = None

        # Mock the async client with a delay to simulate network latency
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "translated"
        mock_response.usage = None

        async def slow_create(**kwargs):
            await asyncio.sleep(0.1)  # 100ms simulated latency
            return mock_response

        mock_client.chat.completions.create = slow_create
        provider.client = mock_client

        # Run 5 translations concurrently
        n = 5
        start = time.monotonic()
        results = await asyncio.gather(
            *[provider.translate(f"text {i}") for i in range(n)]
        )
        elapsed = time.monotonic() - start

        assert len(results) == n
        # If truly concurrent: ~0.1s. If serialized: ~0.5s.
        # Allow generous margin but catch serialization.
        assert elapsed < 0.3, (
            f"5 concurrent calls took {elapsed:.2f}s — likely serialized "
            f"(expected <0.3s for concurrent, got {elapsed:.2f}s)"
        )

    async def test_ark_extracts_cached_tokens_and_summarizes_without_per_request_print(
        self, capsys
    ):
        """ArkProvider should parse cached_tokens but stay quiet by default."""
        from ieeA.translator.ark_provider import ArkProvider

        provider = ArkProvider.__new__(ArkProvider)
        provider.model = "test-model"
        provider.api_key = "test"
        provider.kwargs = {"temperature": 0.0}
        provider._cache_log_verbose = False
        provider._prebuilt_system_prompt = "FIXED_PROMPT"
        provider._prebuilt_batch_prompt = None
        provider._context_id = "ctx-123"
        provider._context_ids = {"individual": "ctx-123"}

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "translated"
        mock_response.usage = {
            "prompt_tokens": 2551,
            "completion_tokens": 133,
            "total_tokens": 2684,
            "prompt_tokens_details": {"cached_tokens": 2535},
        }

        mock_client.context.completions.create = AsyncMock(return_value=mock_response)
        provider.client = mock_client

        result = await provider.translate("hello", glossary_hints=None)

        assert result == "translated"
        assert provider._last_cache_meta is not None
        assert provider._last_cache_meta["cache_hit"] is True
        assert provider._last_cache_meta["cached_tokens"] == 2535
        assert provider._last_cache_meta["prompt_tokens"] == 2551

        out = capsys.readouterr().out
        assert out == ""

        summary = provider.get_cache_stats_summary()
        assert summary["request_count"] == 1
        assert summary["cache_hit_count"] == 1
        assert summary["cache_miss_count"] == 0
        assert summary["cached_tokens_total"] == 2535
        assert summary["total_tokens_total"] == 2684

        lines = provider.format_cache_stats_summary()
        assert isinstance(lines, list)
        assert any("[ARK CACHE SUMMARY]" in line for line in lines)
        assert any("[ARK CACHE TOKENS]" in line and "total=2684" in line for line in lines)

    async def test_ark_cache_stats_aggregate_hit_miss_and_tokens(self):
        """ArkProvider should aggregate cache hit/miss counts and token totals."""
        from ieeA.translator.ark_provider import ArkProvider

        provider = ArkProvider.__new__(ArkProvider)
        provider.model = "test-model"
        provider.api_key = "test"
        provider.kwargs = {"temperature": 0.0}
        provider._cache_log_verbose = False
        provider._prebuilt_system_prompt = None
        provider._prebuilt_batch_prompt = None
        provider._context_id = None
        provider._context_ids = {}

        mock_client = MagicMock()
        hit_response = MagicMock()
        hit_response.choices = [MagicMock()]
        hit_response.choices[0].message.content = "hit"
        hit_response.usage = {
            "prompt_tokens": 100,
            "completion_tokens": 20,
            "total_tokens": 120,
            "prompt_tokens_details": {"cached_tokens": 80},
        }
        miss_response = MagicMock()
        miss_response.choices = [MagicMock()]
        miss_response.choices[0].message.content = "miss"
        miss_response.usage = {
            "prompt_tokens": 90,
            "completion_tokens": 30,
            "total_tokens": 120,
            "prompt_tokens_details": {"cached_tokens": 0},
        }
        mock_client.chat.completions.create = AsyncMock(
            side_effect=[hit_response, miss_response]
        )
        provider.client = mock_client

        assert await provider.translate("a") == "hit"
        assert await provider.translate("b") == "miss"

        summary = provider.get_cache_stats_summary()
        assert summary["request_count"] == 2
        assert summary["cache_hit_count"] == 1
        assert summary["cache_miss_count"] == 1
        assert summary["cached_tokens_total"] == 80
        assert summary["prompt_tokens_total"] == 190
        assert summary["completion_tokens_total"] == 50
        assert summary["total_tokens_total"] == 240

    async def test_ark_cache_stats_track_missing_usage_without_polluting_totals(self):
        """Responses without usage should not affect token totals and should be counted separately."""
        from ieeA.translator.ark_provider import ArkProvider

        provider = ArkProvider.__new__(ArkProvider)
        provider.model = "test-model"
        provider.api_key = "test"
        provider.kwargs = {"temperature": 0.0}
        provider._cache_log_verbose = False
        provider._prebuilt_system_prompt = None
        provider._prebuilt_batch_prompt = None
        provider._context_id = None
        provider._context_ids = {}

        mock_client = MagicMock()
        no_usage_response = MagicMock()
        no_usage_response.choices = [MagicMock()]
        no_usage_response.choices[0].message.content = "ok"
        no_usage_response.usage = None
        mock_client.chat.completions.create = AsyncMock(return_value=no_usage_response)
        provider.client = mock_client

        assert await provider.translate("hello") == "ok"

        summary = provider.get_cache_stats_summary()
        assert summary["request_count"] == 0
        assert summary["cache_hit_count"] == 0
        assert summary["cache_miss_count"] == 0
        assert summary["cached_tokens_total"] == 0
        assert summary["total_tokens_total"] == 0
        assert summary["missing_usage_count"] == 1

    async def test_pipeline_captures_provider_cache_meta(self):
        """Pipeline metadata should include provider_cache_meta from provider side-channel."""
        from ieeA.translator.pipeline import TranslationPipeline

        provider = AsyncMock()

        async def translate_side_effect(**kwargs):
            provider._last_cache_meta = {
                "provider": "ark",
                "cache_hit": True,
                "cached_tokens": 120,
                "prompt_tokens": 140,
                "completion_tokens": 20,
                "total_tokens": 160,
            }
            return "你好"

        provider.translate = AsyncMock(side_effect=translate_side_effect)

        pipeline = TranslationPipeline(provider=provider)
        chunk = await pipeline.translate_chunk("hello", chunk_id="chunk-1")

        cache_meta = chunk.metadata.get("provider_cache_meta")
        assert isinstance(cache_meta, dict)
        assert cache_meta["cache_hit"] is True
        assert cache_meta["cached_tokens"] == 120

    async def test_pipeline_translate_batch_passes_prompt_variant_without_mutating_shared_prompt(
        self,
    ):
        """Batch path should use explicit prompt_variant, not swap provider shared prompt."""
        from ieeA.translator.pipeline import TranslationPipeline

        provider = AsyncMock()
        provider._prebuilt_system_prompt = "INDIVIDUAL_PROMPT"
        provider._prebuilt_batch_prompt = "BATCH_PROMPT"
        provider._last_cache_meta = None

        async def translate_side_effect(**kwargs):
            assert kwargs["prompt_variant"] == "batch"
            assert provider._prebuilt_system_prompt == "INDIVIDUAL_PROMPT"
            return "[1] 你好"

        provider.translate = AsyncMock(side_effect=translate_side_effect)

        pipeline = TranslationPipeline(provider=provider)
        results = await pipeline.translate_batch(
            [{"chunk_id": "c1", "content": "hello"}],
            context="Academic Paper",
        )

        assert len(results) == 1
        assert results[0].translation == "你好"

    async def test_pipeline_warms_required_prompt_variants_before_translation(self):
        """Pipeline should prewarm both batch and individual prompt variants when both are used."""
        from ieeA.translator.pipeline import TranslationPipeline

        provider = AsyncMock()
        provider._last_cache_meta = None
        provider.prepare_prompt_cache_variants = AsyncMock()

        async def translate_side_effect(**kwargs):
            if kwargs.get("prompt_variant") == "batch":
                return "[1] 一"
            return "一"

        provider.translate = AsyncMock(side_effect=translate_side_effect)

        pipeline = TranslationPipeline(
            provider=provider,
            batch_short_threshold=10,
            batch_max_chars=100,
            sequential_mode=True,
        )

        chunks = [
            {"chunk_id": "short-1", "content": "hi"},
            {"chunk_id": "long-1", "content": "x" * 20},
        ]

        await pipeline.translate_document(chunks=chunks, context="Academic Paper")

        provider.prepare_prompt_cache_variants.assert_awaited_once()
        call_kwargs = provider.prepare_prompt_cache_variants.call_args.kwargs
        assert call_kwargs["prompt_variants"] == ["batch", "individual"]

    async def test_ark_translate_uses_variant_specific_context_id(self):
        """ArkProvider should choose context_id by prompt_variant."""
        from ieeA.translator.ark_provider import ArkProvider

        provider = ArkProvider.__new__(ArkProvider)
        provider.model = "test-model"
        provider.api_key = "test"
        provider.kwargs = {"temperature": 0.0}
        provider._prebuilt_system_prompt = "INDIVIDUAL_PROMPT"
        provider._prebuilt_batch_prompt = "BATCH_PROMPT"
        provider._context_ids = {"individual": "ctx-ind", "batch": "ctx-batch"}
        provider._context_id = "ctx-ind"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "translated"
        mock_response.usage = None
        mock_client.context.completions.create = AsyncMock(return_value=mock_response)
        provider.client = mock_client

        result = await provider.translate(
            "hello",
            glossary_hints=None,
            prompt_variant="batch",
        )

        assert result == "translated"
        call_kwargs = mock_client.context.completions.create.call_args.kwargs
        assert call_kwargs["context_id"] == "ctx-batch"

    async def test_ark_setup_context_caches_few_shot_prefix(self):
        """ArkProvider setup_context should cache system + few-shot messages as prefix."""
        from ieeA.translator.ark_provider import ArkProvider

        provider = ArkProvider.__new__(ArkProvider)
        provider.model = "test-model"
        provider.api_key = "test"
        provider.kwargs = {"temperature": 0.0}
        provider._prebuilt_system_prompt = "INDIVIDUAL_PROMPT"
        provider._prebuilt_batch_prompt = "BATCH_PROMPT"
        provider._context_ids = {}
        provider._context_id = None

        mock_client = MagicMock()
        mock_context = MagicMock()
        mock_context.id = "ctx-ind"
        mock_client.context.create = AsyncMock(return_value=mock_context)
        provider.client = mock_client

        few_shot = [{"source": "A", "target": "甲"}]
        await provider.setup_context(prompt_variant="individual", few_shot_examples=few_shot)

        create_kwargs = mock_client.context.create.call_args.kwargs
        messages = create_kwargs["messages"]
        assert messages[0] == {"role": "system", "content": "INDIVIDUAL_PROMPT"}
        assert messages[1] == {"role": "user", "content": "A"}
        assert messages[2] == {"role": "assistant", "content": "甲"}

    async def test_ark_batch_context_rebuild_does_not_overwrite_individual_context(self):
        """Rebuilding expired batch context should keep individual context_id intact."""
        from ieeA.translator.ark_provider import ArkProvider

        provider = ArkProvider.__new__(ArkProvider)
        provider.model = "test-model"
        provider.api_key = "test"
        provider.kwargs = {"temperature": 0.0}
        provider._prebuilt_system_prompt = "INDIVIDUAL_PROMPT"
        provider._prebuilt_batch_prompt = "BATCH_PROMPT"
        provider._context_ids = {"individual": "ctx-ind", "batch": "ctx-batch-old"}
        provider._context_prefix_keys = {}
        provider._context_setup_locks = {}
        provider._context_id = "ctx-ind"

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "translated"
        mock_response.usage = None

        async def context_completion_side_effect(**kwargs):
            if kwargs["context_id"] == "ctx-batch-old":
                raise RuntimeError("expired")
            return mock_response

        mock_client.context.completions.create = AsyncMock(
            side_effect=context_completion_side_effect
        )
        new_context = MagicMock()
        new_context.id = "ctx-batch-new"
        mock_client.context.create = AsyncMock(return_value=new_context)
        provider.client = mock_client

        result = await provider.translate(
            "hello",
            glossary_hints=None,
            prompt_variant="batch",
        )

        assert result == "translated"
        assert provider._context_ids["batch"] == "ctx-batch-new"
        assert provider._context_ids["individual"] == "ctx-ind"
        assert provider._context_id == "ctx-ind"
