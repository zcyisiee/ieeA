from typing import Optional, Any
from .llm_base import LLMProvider
from .openai_provider import OpenAIProvider
from .claude_provider import ClaudeProvider
from .qwen_provider import QwenProvider
from .doubao_provider import DoubaoProvider

def get_provider(provider_name: str, model: str, api_key: Optional[str] = None, **kwargs: Any) -> LLMProvider:
    """
    Factory function to get an LLM provider instance.

    Args:
        provider_name: The name of the provider (openai, claude, qwen, doubao).
        model: The model name to use.
        api_key: Optional API key.
        **kwargs: Additional keyword arguments to pass to the provider constructor.

    Returns:
        An instance of LLMProvider.
    """
    provider_name = provider_name.lower()
    if provider_name == "openai":
        return OpenAIProvider(model=model, api_key=api_key, **kwargs)
    elif provider_name in ["claude", "anthropic"]:
        return ClaudeProvider(model=model, api_key=api_key, **kwargs)
    elif provider_name in ["qwen", "dashscope"]:
        return QwenProvider(model=model, api_key=api_key, **kwargs)
    elif provider_name in ["doubao", "volcengine", "ark"]:
        return DoubaoProvider(model=model, api_key=api_key, **kwargs)
    else:
        raise ValueError(f"Unknown provider: {provider_name}. Supported providers: openai, claude, qwen, doubao")

__all__ = ["LLMProvider", "OpenAIProvider", "ClaudeProvider", "QwenProvider", "DoubaoProvider", "get_provider"]
