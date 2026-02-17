from typing import Optional, Any
from .llm_base import LLMProvider
from .openai_provider import OpenAIProvider
from .openai_coding_provider import OpenAICodingProvider
from .anthropic_provider import AnthropicProvider
from .http_provider import DirectHTTPProvider


def _normalize_openai_base_url(endpoint: Optional[str]) -> Optional[str]:
    """Normalize OpenAI-compatible base URL to avoid duplicate route suffix."""
    if not endpoint:
        return endpoint
    suffix = "/chat/completions"
    if endpoint.endswith(suffix):
        return endpoint[: -len(suffix)]
    return endpoint


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
        normalized_endpoint = _normalize_openai_base_url(endpoint)
        return OpenAIProvider(
            model=model, api_key=key, base_url=normalized_endpoint, **kwargs
        )
    elif sdk == "openai-coding":
        normalized_endpoint = _normalize_openai_base_url(endpoint)
        return OpenAICodingProvider(
            model=model, api_key=key, base_url=normalized_endpoint, **kwargs
        )
    elif sdk == "anthropic":
        return AnthropicProvider(model=model, api_key=key, **kwargs)
    elif sdk is None:
        return DirectHTTPProvider(model=model, api_key=key, endpoint=endpoint, **kwargs)
    else:
        raise ValueError(
            f"Unknown sdk: {sdk}. Supported: openai, openai-coding, anthropic, None"
        )


__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "OpenAICodingProvider",
    "AnthropicProvider",
    "DirectHTTPProvider",
    "get_sdk_client",
]
