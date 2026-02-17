from typing import Optional, Any
from .llm_base import LLMProvider
from .openai_provider import OpenAIProvider
from .openai_coding_provider import OpenAICodingProvider
from .anthropic_provider import AnthropicProvider
from .anthropic_coding_provider import AnthropicCodingProvider
from .http_provider import DirectHTTPProvider
from .ark_provider import ArkProvider


def _normalize_openai_base_url(endpoint: Optional[str]) -> Optional[str]:
    """Normalize OpenAI-compatible base URL to avoid duplicate route suffix."""
    if not endpoint:
        return endpoint
    suffix = "/chat/completions"
    if endpoint.endswith(suffix):
        return endpoint[: -len(suffix)]
    return endpoint


def _normalize_anthropic_base_url(endpoint: Optional[str]) -> Optional[str]:
    if not endpoint:
        return endpoint
    normalized = endpoint.rstrip("/")
    for suffix in ("/v1/messages", "/v1", "/messages"):
        if normalized.endswith(suffix):
            return normalized[: -len(suffix)]
    return normalized


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
        sdk: The SDK to use (openai, openai-coding, anthropic, anthropic-coding, or None for direct HTTP).
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
        normalized_endpoint = _normalize_anthropic_base_url(endpoint)
        return AnthropicProvider(
            model=model,
            api_key=key,
            base_url=normalized_endpoint,
            **kwargs,
        )
    elif sdk == "anthropic-coding":
        normalized_endpoint = _normalize_anthropic_base_url(endpoint)
        return AnthropicCodingProvider(
            model=model,
            api_key=key,
            base_url=normalized_endpoint,
            **kwargs,
        )
    elif sdk == "ark":
        return ArkProvider(model=model, api_key=key, base_url=endpoint, **kwargs)
    elif sdk is None:
        return DirectHTTPProvider(model=model, api_key=key, endpoint=endpoint, **kwargs)
    else:
        raise ValueError(
            "Unknown sdk: "
            f"{sdk}. Supported: openai, openai-coding, anthropic, anthropic-coding, ark, None"
        )


__all__ = [
    "LLMProvider",
    "OpenAIProvider",
    "OpenAICodingProvider",
    "AnthropicProvider",
    "AnthropicCodingProvider",
    "DirectHTTPProvider",
    "ArkProvider",
    "get_sdk_client",
]
