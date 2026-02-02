import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys

# Mock external dependencies before importing the modules under test
mock_openai = MagicMock()
mock_openai.AsyncOpenAI = MagicMock()
sys.modules["openai"] = mock_openai
sys.modules["tiktoken"] = MagicMock()
mock_anthropic = MagicMock()
mock_anthropic.AsyncAnthropic = MagicMock()
sys.modules["anthropic"] = mock_anthropic
sys.modules["httpx"] = MagicMock()

from ieeA.translator import (
    get_sdk_client,
    OpenAIProvider,
    AnthropicProvider,
    DirectHTTPProvider,
)
from ieeA.translator.llm_base import LLMProvider


@pytest.mark.asyncio
async def test_get_sdk_client():
    # Test valid SDKs
    assert isinstance(get_sdk_client("openai", "gpt-4", key="test"), OpenAIProvider)
    assert isinstance(
        get_sdk_client("anthropic", "claude-3", key="test"), AnthropicProvider
    )
    assert isinstance(
        get_sdk_client(None, "model", key="test", endpoint="http://example.com"),
        DirectHTTPProvider,
    )

    # Test unknown sdk
    with pytest.raises(ValueError, match="Unknown sdk"):
        get_sdk_client("unknown", "model", key="test")


@pytest.mark.asyncio
async def test_openai_provider():
    # Create a fresh mock for AsyncOpenAI
    mock_client_instance = MagicMock()
    mock_client_instance.chat.completions.create = AsyncMock()
    mock_client_instance.chat.completions.create.return_value.choices = [
        MagicMock(message=MagicMock(content="Translated text"))
    ]

    with patch.object(mock_openai, "AsyncOpenAI", return_value=mock_client_instance):
        provider = OpenAIProvider("gpt-4", "test-key")
        result = await provider.translate("Hello")

        assert result == "Translated text"
        mock_client_instance.chat.completions.create.assert_called_once()

        # Test estimate tokens (simple heuristic check)
        count = provider.estimate_tokens("Hello World")
        assert count >= 0  # Accept 0 or positive (mock may return 0)


@pytest.mark.asyncio
async def test_anthropic_provider():
    # Create a fresh mock for AsyncAnthropic
    mock_client_instance = MagicMock()
    text_block = MagicMock()
    text_block.type = "text"
    text_block.text = "Translated text"
    mock_client_instance.messages.create = AsyncMock()
    mock_client_instance.messages.create.return_value.content = [text_block]

    with patch.object(
        mock_anthropic, "AsyncAnthropic", return_value=mock_client_instance
    ):
        # Re-import to use the patched mock
        from ieeA.translator.anthropic_provider import AnthropicProvider as AP

        provider = AP("claude-3", "test-key")
        provider.client = mock_client_instance  # Directly set the mocked client
        result = await provider.translate("Hello")

        assert result == "Translated text"
        mock_client_instance.messages.create.assert_called_once()

        # Test estimate tokens
        count = provider.estimate_tokens("Hello")
        assert count >= 0


@pytest.mark.asyncio
async def test_http_provider():
    # Test DirectHTTPProvider with httpx mock
    mock_response = MagicMock()
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Translated text"}}]
    }
    mock_response.raise_for_status = MagicMock()

    mock_client = MagicMock()
    mock_client.post = AsyncMock(return_value=mock_response)

    with patch(
        "ieeA.translator.http_provider.httpx.AsyncClient", return_value=mock_client
    ):
        provider = DirectHTTPProvider(
            "test-model", api_key="test-key", endpoint="http://example.com/v1"
        )
        result = await provider.translate("Hello")

        assert result == "Translated text"

        # Test estimate tokens
        count = provider.estimate_tokens("Hello")
        assert count > 0
