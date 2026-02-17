"""Tests for provider cache mechanisms."""

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
