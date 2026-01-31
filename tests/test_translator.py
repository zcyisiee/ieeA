import pytest
from unittest.mock import MagicMock, patch, AsyncMock
import sys

# Mock external dependencies before importing the modules under test
sys.modules["openai"] = MagicMock()
sys.modules["tiktoken"] = MagicMock()
sys.modules["anthropic"] = MagicMock()
sys.modules["dashscope"] = MagicMock()
sys.modules["volcenginesdkarkruntime"] = MagicMock()

from ieet.translator import get_provider, OpenAIProvider, ClaudeProvider, QwenProvider, DoubaoProvider
from ieet.translator.llm_base import LLMProvider

@pytest.mark.asyncio
async def test_get_provider():
    # Test valid providers
    assert isinstance(get_provider("openai", "gpt-4"), OpenAIProvider)
    assert isinstance(get_provider("claude", "claude-3"), ClaudeProvider)
    assert isinstance(get_provider("anthropic", "claude-3"), ClaudeProvider)
    assert isinstance(get_provider("qwen", "qwen-max", api_key="test"), QwenProvider)
    assert isinstance(get_provider("doubao", "doubao-pro"), DoubaoProvider)

    # Test unknown provider
    with pytest.raises(ValueError, match="Unknown provider"):
        get_provider("unknown", "model")

@pytest.mark.asyncio
async def test_openai_provider():
    with patch("ieet.translator.openai_provider.AsyncOpenAI") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.chat.completions.create = AsyncMock()
        mock_instance.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Translated text"))
        ]

        provider = OpenAIProvider("gpt-4", "test-key")
        result = await provider.translate("Hello")
        
        assert result == "Translated text"
        mock_instance.chat.completions.create.assert_called_once()
        
        # Test estimate tokens
        with patch("ieet.translator.openai_provider.HAS_TIKTOKEN", False):
            count = provider.estimate_tokens("Hello")
            assert count > 0

@pytest.mark.asyncio
async def test_claude_provider():
    with patch("ieet.translator.claude_provider.AsyncAnthropic") as mock_client:
        mock_instance = mock_client.return_value
        # Mocking the content block structure
        text_block = MagicMock()
        text_block.type = 'text'
        text_block.text = "Translated text"
        
        mock_instance.messages.create = AsyncMock()
        mock_instance.messages.create.return_value.content = [text_block]

        provider = ClaudeProvider("claude-3", "test-key")
        result = await provider.translate("Hello")
        
        assert result == "Translated text"
        mock_instance.messages.create.assert_called_once()
        
        # Test estimate tokens
        count = provider.estimate_tokens("Hello")
        assert count > 0

@pytest.mark.asyncio
async def test_qwen_provider():
    # Mock dashscope
    with patch("ieet.translator.qwen_provider.dashscope") as mock_dashscope:
        mock_dashscope.Generation.call = MagicMock()
        
        # Mock return value of call
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.output.choices = [
            MagicMock(message=MagicMock(content="Translated text"))
        ]
        mock_dashscope.Generation.call.return_value = mock_response
        
        # We need to mock HTTPStatus since it's used in the module
        with patch("ieet.translator.qwen_provider.HTTPStatus") as mock_http_status:
            mock_http_status.OK = 200
            
            provider = QwenProvider("qwen-max", "test-key")
            result = await provider.translate("Hello")
            
            assert result == "Translated text"
            
            # Test estimate tokens
            count = provider.estimate_tokens("Hello")
            assert count > 0

@pytest.mark.asyncio
async def test_doubao_provider():
    with patch("ieet.translator.doubao_provider.AsyncArk") as mock_client:
        mock_instance = mock_client.return_value
        mock_instance.chat.completions.create = AsyncMock()
        mock_instance.chat.completions.create.return_value.choices = [
            MagicMock(message=MagicMock(content="Translated text"))
        ]

        provider = DoubaoProvider("doubao-pro", "test-key")
        result = await provider.translate("Hello")
        
        assert result == "Translated text"
        mock_instance.chat.completions.create.assert_called_once()
        
        # Test estimate tokens
        count = provider.estimate_tokens("Hello")
        assert count > 0
