from typing import Optional, Any
from .llm_base import LLMProvider
from .openai_provider import OpenAIProvider
from .anthropic_provider import AnthropicProvider
from .http_provider import DirectHTTPProvider


def get_sdk_client(
    sdk: Optional[str],
    model: str,
    key: Optional[str] = None,
    endpoint: Optional[str] = None,
    **kwargs: Any,
) -> LLMProvider:
    """
    Factory function to get an LLM SDK client instance.

    Args:
        sdk: The SDK to use (openai, anthropic, or None for direct HTTP).
        model: The model name to use.
        key: Optional API key.
        endpoint: Optional API endpoint URL.
        **kwargs: Additional keyword arguments to pass to the provider constructor.

    Returns:
        An instance of LLMProvider.
    """
    if sdk == "openai":
        return OpenAIProvider(model=model, api_key=key, base_url=endpoint, **kwargs)
    elif sdk == "anthropic":
        return AnthropicProvider(model=model, api_key=key, **kwargs)
    elif sdk is None:
        return DirectHTTPProvider(model=model, api_key=key, endpoint=endpoint, **kwargs)
    else:
        raise ValueError(f"Unknown sdk: {sdk}. Supported: openai, anthropic, None")


__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "AnthropicProvider",
    "DirectHTTPProvider",
    "get_sdk_client",
]
