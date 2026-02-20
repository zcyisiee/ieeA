"""Tests for BailianProvider (Alibaba Bailian/DashScope).

Tests cover:
- Inheritance from OpenAIProvider
- Initialization with default base_url
- Message format with cache_control
- Cache metadata extraction
- Factory function integration
- Configuration validation
- Error handling
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch


class TestBailianProviderInheritance:
    """Test BailianProvider inheritance structure."""

    def test_bailian_provider_extends_openai_provider(self):
        """BailianProvider should be a subclass of OpenAIProvider."""
        from ieeA.translator.bailian_provider import BailianProvider
        from ieeA.translator.openai_provider import OpenAIProvider

        assert issubclass(BailianProvider, OpenAIProvider)

    def test_bailian_provider_extends_llm_provider(self):
        """BailianProvider should ultimately extend LLMProvider."""
        from ieeA.translator.bailian_provider import BailianProvider
        from ieeA.translator.llm_base import LLMProvider

        assert issubclass(BailianProvider, LLMProvider)

    def test_bailian_provider_has_required_methods(self):
        """BailianProvider should have all required methods."""
        from ieeA.translator.bailian_provider import BailianProvider

        assert hasattr(BailianProvider, "translate")
        assert hasattr(BailianProvider, "ping")
        assert hasattr(BailianProvider, "estimate_tokens")
        assert hasattr(BailianProvider, "_extract_cache_meta")


class TestBailianProviderInitialization:
    """Test BailianProvider initialization."""

    def test_prebuilt_prompt_attributes_initialized(self):
        """Prebuilt prompt attributes should be initialized to None."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_openai.AsyncOpenAI = MagicMock()
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")

            assert provider._prebuilt_system_prompt is None
            assert provider._prebuilt_batch_prompt is None


class TestBailianProviderMessageFormat:
    """Test BailianProvider message format with cache_control."""

    async def test_system_message_is_array_with_cache_control(self):
        """System message should be array format with cache_control."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_response.usage = None
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")
            provider._prebuilt_system_prompt = "FIXED_SYSTEM_PROMPT"

            result = await provider.translate("test text", glossary_hints=None)

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])

            assert messages[0]["role"] == "system"
            assert isinstance(messages[0]["content"], list)
            assert len(messages[0]["content"]) == 1
            assert messages[0]["content"][0]["type"] == "text"
            assert messages[0]["content"][0]["text"] == "FIXED_SYSTEM_PROMPT"
            assert messages[0]["content"][0]["cache_control"] == {"type": "ephemeral"}

    async def test_system_message_cache_control_structure(self):
        """Cache control should have exactly the right structure."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_response.usage = None
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")

            await provider.translate("test text")

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])
            system_content = messages[0]["content"]

            assert isinstance(system_content, list)
            assert len(system_content) == 1
            block = system_content[0]
            assert block["type"] == "text"
            assert "text" in block
            assert "cache_control" in block
            assert block["cache_control"]["type"] == "ephemeral"

    async def test_prebuilt_prompt_bypass(self):
        """When _prebuilt_system_prompt is set and no glossary, use it directly."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_response.usage = None
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")
            provider._prebuilt_system_prompt = "PREBUILT_PROMPT"

            result = await provider.translate("test text", glossary_hints=None)

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])
            assert messages[0]["content"][0]["text"] == "PREBUILT_PROMPT"

    async def test_prebuilt_ignored_when_glossary_provided(self):
        """When glossary_hints is provided, prebuilt prompt should NOT be used."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_response.usage = None
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")
            provider._prebuilt_system_prompt = "PREBUILT_PROMPT"

            result = await provider.translate("test text", glossary_hints={"AI": "AI"})

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])
            system_text = messages[0]["content"][0]["text"]
            assert system_text != "PREBUILT_PROMPT"
            assert "AI" in system_text

    async def test_few_shot_examples_in_messages(self):
        """Few-shot examples should be included in messages."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_response.usage = None
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")

            few_shots = [
                {"source": "Hello", "target": "你好"},
                {"source": "World", "target": "世界"},
            ]

            result = await provider.translate("test", few_shot_examples=few_shots)

            call_args = mock_client.chat.completions.create.call_args
            messages = call_args.kwargs.get("messages", [])

            assert len(messages) == 6
            assert messages[1] == {"role": "user", "content": "Hello"}
            assert messages[2] == {"role": "assistant", "content": "你好"}
            assert messages[3] == {"role": "user", "content": "World"}
            assert messages[4] == {"role": "assistant", "content": "世界"}
            assert messages[5] == {"role": "user", "content": "test"}


class TestBailianProviderCacheMeta:
    """Test BailianProvider cache metadata extraction."""

    def test_extract_cache_meta_with_cached_tokens(self):
        """Should correctly extract cached_tokens and cache_creation_input_tokens."""
        from ieeA.translator.bailian_provider import BailianProvider

        provider = BailianProvider.__new__(BailianProvider)

        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 1100
        mock_response.usage.prompt_tokens_details.cached_tokens = 800
        mock_response.usage.prompt_tokens_details.cache_creation_input_tokens = 50

        result = provider._extract_cache_meta(mock_response)

        assert result is not None
        assert result["provider"] == "bailian"
        assert result["cache_hit"] is True
        assert result["cached_tokens"] == 800
        assert result["cache_creation_input_tokens"] == 50
        assert result["prompt_tokens"] == 1000
        assert result["completion_tokens"] == 100
        assert result["total_tokens"] == 1100

    def test_extract_cache_meta_no_cache_hit(self):
        """Should correctly handle case with no cache hit."""
        from ieeA.translator.bailian_provider import BailianProvider

        provider = BailianProvider.__new__(BailianProvider)

        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 1100
        mock_response.usage.prompt_tokens_details.cached_tokens = 0
        mock_response.usage.prompt_tokens_details.cache_creation_input_tokens = 0

        result = provider._extract_cache_meta(mock_response)

        assert result is not None
        assert result["cache_hit"] is False
        assert result["cached_tokens"] == 0
        assert result["cache_creation_input_tokens"] == 0

    def test_extract_cache_meta_missing_details(self):
        """Should handle missing prompt_tokens_details gracefully."""
        from ieeA.translator.bailian_provider import BailianProvider

        provider = BailianProvider.__new__(BailianProvider)

        mock_response = MagicMock()
        mock_response.usage.prompt_tokens = 1000
        mock_response.usage.completion_tokens = 100
        mock_response.usage.total_tokens = 1100
        del mock_response.usage.prompt_tokens_details

        result = provider._extract_cache_meta(mock_response)

        assert result is not None
        assert result["cached_tokens"] == 0
        assert result["cache_creation_input_tokens"] == 0
        assert result["cache_hit"] is False

    def test_extract_cache_meta_missing_usage(self):
        """Should return None when usage is missing."""
        from ieeA.translator.bailian_provider import BailianProvider

        provider = BailianProvider.__new__(BailianProvider)

        mock_response = MagicMock()
        del mock_response.usage

        result = provider._extract_cache_meta(mock_response)

        assert result is None

    def test_extract_cache_meta_with_dict_usage(self):
        """Should handle dict-style usage object (from some API responses)."""
        from ieeA.translator.bailian_provider import BailianProvider

        provider = BailianProvider.__new__(BailianProvider)

        mock_response = {
            "usage": {
                "prompt_tokens": 1000,
                "completion_tokens": 100,
                "total_tokens": 1100,
                "prompt_tokens_details": {
                    "cached_tokens": 900,
                    "cache_creation_input_tokens": 100,
                },
            }
        }

        result = provider._extract_cache_meta(mock_response)

        assert result is not None
        assert result["cached_tokens"] == 900
        assert result["cache_creation_input_tokens"] == 100
        assert result["cache_hit"] is True

    async def test_cache_meta_stored_on_translate(self):
        """Cache metadata should be stored in _last_cache_meta after translate."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_response.usage.prompt_tokens = 1000
            mock_response.usage.completion_tokens = 100
            mock_response.usage.total_tokens = 1100
            mock_response.usage.prompt_tokens_details.cached_tokens = 800
            mock_response.usage.prompt_tokens_details.cache_creation_input_tokens = 50
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")

            result = await provider.translate("test text")

            assert provider._last_cache_meta is not None
            assert provider._last_cache_meta["cached_tokens"] == 800
            assert provider._last_cache_meta["cache_creation_input_tokens"] == 50

    async def test_cache_meta_printed(self, capsys):
        """Cache metadata should be printed after translate."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "translated"
            mock_response.usage.prompt_tokens = 1000
            mock_response.usage.completion_tokens = 100
            mock_response.usage.total_tokens = 1100
            mock_response.usage.prompt_tokens_details.cached_tokens = 800
            mock_response.usage.prompt_tokens_details.cache_creation_input_tokens = 50
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")

            result = await provider.translate("test text")

            out = capsys.readouterr().out
            assert "[BAILIAN CACHE]" in out
            assert "cached_tokens=800" in out
            assert "cache_creation=50" in out
            assert "hit=True" in out


class TestBailianProviderFactory:
    """Test factory function integration."""

    def test_factory_returns_bailian_provider(self):
        """get_sdk_client('bailian', ...) should return BailianProvider instance."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_openai.AsyncOpenAI = MagicMock()
            mock_openai.Timeout = MagicMock()

            from ieeA.translator import get_sdk_client
            from ieeA.translator.bailian_provider import BailianProvider

            provider = get_sdk_client("bailian", model="qwen-max", key="test-key")

            assert isinstance(provider, BailianProvider)


class TestBailianProviderConfig:
    """Test configuration validation."""

    def test_config_accepts_bailian_sdk(self):
        """LLMConfig(sdk='bailian') should succeed without error."""
        from ieeA.rules.config import LLMConfig

        cfg = LLMConfig(sdk="bailian")
        assert cfg.sdk == "bailian"

    def test_config_rejects_invalid_sdk(self):
        """LLMConfig(sdk='invalid') should raise ValueError."""
        from ieeA.rules.config import LLMConfig

        with pytest.raises(ValueError, match="sdk must be"):
            LLMConfig(sdk="invalid")


class TestBailianProviderErrorHandling:
    """Test error handling."""

    async def test_api_error_raises_runtime_error(self):
        """API errors should be wrapped in RuntimeError."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("API connection failed")
            )
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")

            with pytest.raises(RuntimeError, match="Bailian API error"):
                await provider.translate("test text")

    async def test_api_error_includes_original_message(self):
        """RuntimeError should include the original error message."""
        with patch("ieeA.translator.openai_provider.openai") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create = AsyncMock(
                side_effect=Exception("Rate limit exceeded")
            )
            mock_openai.AsyncOpenAI.return_value = mock_client
            mock_openai.Timeout = MagicMock()

            from ieeA.translator.bailian_provider import BailianProvider

            provider = BailianProvider(model="qwen-max", api_key="test-key")

            with pytest.raises(RuntimeError) as exc_info:
                await provider.translate("test text")

            assert "Rate limit exceeded" in str(exc_info.value)


class TestBailianProviderGetFieldHelper:
    """Test the _get_field helper method."""

    def test_get_field_from_object(self):
        """Should get attribute from object."""
        from ieeA.translator.bailian_provider import BailianProvider

        class MockObj:
            attr = "value"

        result = BailianProvider._get_field(MockObj(), "attr")
        assert result == "value"

    def test_get_field_from_dict(self):
        """Should get key from dict."""
        from ieeA.translator.bailian_provider import BailianProvider

        data = {"key": "value"}
        result = BailianProvider._get_field(data, "key")
        assert result == "value"

    def test_get_field_with_default(self):
        """Should return default when field missing."""
        from ieeA.translator.bailian_provider import BailianProvider

        class MockObj:
            pass

        result = BailianProvider._get_field(MockObj(), "missing", "default")
        assert result == "default"

    def test_get_field_from_none(self):
        """Should return default when obj is None."""
        from ieeA.translator.bailian_provider import BailianProvider

        result = BailianProvider._get_field(None, "key", "default")
        assert result == "default"
