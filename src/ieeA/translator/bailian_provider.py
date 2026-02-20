# pyright: reportPossiblyUnboundVariable=false, reportOptionalMemberAccess=false
"""Alibaba Bailian (DashScope) provider with explicit cache control."""

from typing import Optional, Dict, List, Any, cast

from .openai_provider import OpenAIProvider
from .prompts import build_system_prompt

# Type hint for OpenAI client
AsyncOpenAI: Any = None
try:
    from openai import AsyncOpenAI
except ImportError:
    pass


class BailianProvider(OpenAIProvider):
    """Alibaba Bailian (DashScope) provider using explicit cache_control.

    Uses OpenAI-compatible API with array-formatted system messages for caching.
    Base URL: https://dashscope.aliyuncs.com/compatible-mode/v1
    """

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs: Any,
    ):
        # Use Bailian's default endpoint if not specified
        if base_url is None:
            base_url = "https://dashscope.aliyuncs.com/compatible-mode/v1"

        super().__init__(model, api_key, base_url, **kwargs)
        self._prebuilt_system_prompt: Optional[str] = None
        self._prebuilt_batch_prompt: Optional[str] = None

    @staticmethod
    def _get_field(obj: Any, key: str, default: Any = None) -> Any:
        """Safely get field from object or dict."""
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _extract_cache_meta(self, response: Any) -> Optional[Dict[str, Any]]:
        """Extract cache metadata from response.

        Args:
            response: The API response object.

        Returns:
            Dict with cache metadata or None if not available.
        """

        def _to_int(value: Any) -> int:
            try:
                if isinstance(value, bool):
                    return int(value)
                if isinstance(value, (int, float, str)):
                    return int(value)
            except (TypeError, ValueError):
                pass
            return 0

        usage = self._get_field(response, "usage", None)
        if usage is None:
            return None

        prompt_tokens = _to_int(self._get_field(usage, "prompt_tokens", 0))
        completion_tokens = _to_int(self._get_field(usage, "completion_tokens", 0))
        total_tokens = _to_int(self._get_field(usage, "total_tokens", 0))

        # Extract prompt token details for cache info
        prompt_details = self._get_field(usage, "prompt_tokens_details", None)
        cached_tokens = _to_int(self._get_field(prompt_details, "cached_tokens", 0))
        cache_creation_input_tokens = _to_int(
            self._get_field(prompt_details, "cache_creation_input_tokens", 0)
        )

        return {
            "provider": "bailian",
            "cache_hit": cached_tokens > 0,
            "cached_tokens": cached_tokens,
            "cache_creation_input_tokens": cache_creation_input_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    @staticmethod
    def _print_cache_meta(cache_meta: Dict[str, Any]) -> None:
        """Print cache metadata for debugging."""
        print(
            "[BAILIAN CACHE] "
            f"hit={cache_meta.get('cache_hit')} "
            f"cached_tokens={cache_meta.get('cached_tokens')} "
            f"cache_creation={cache_meta.get('cache_creation_input_tokens')} "
            f"prompt_tokens={cache_meta.get('prompt_tokens')} "
            f"completion_tokens={cache_meta.get('completion_tokens')} "
            f"total_tokens={cache_meta.get('total_tokens')}"
        )

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> str:
        """Translate text using Bailian API with cache control.

        Formats system message as an array with cache_control for explicit caching.

        Args:
            text: Text to translate.
            context: Optional context for translation.
            glossary_hints: Optional glossary hints.
            few_shot_examples: Optional few-shot examples.
            custom_system_prompt: Optional custom system prompt.

        Returns:
            Translated text.
        """
        messages: List[Dict[str, Any]] = []

        # Build system content
        if self._prebuilt_system_prompt is not None and glossary_hints is None:
            system_content = self._prebuilt_system_prompt
        else:
            system_content = build_system_prompt(
                glossary_hints=glossary_hints,
                context=context,
                few_shot_examples=few_shot_examples,
                custom_system_prompt=custom_system_prompt,
            )

        # Format system message as array with cache_control
        messages.append(
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": system_content,
                        "cache_control": {"type": "ephemeral"},
                    }
                ],
            }
        )

        # Few-shot examples
        if few_shot_examples:
            for example in few_shot_examples:
                messages.append({"role": "user", "content": example.get("source", "")})
                messages.append(
                    {"role": "assistant", "content": example.get("target", "")}
                )

        # User message
        messages.append({"role": "user", "content": text})

        try:
            response = await self.client.chat.completions.create(  # type: ignore
                model=self.model,
                messages=messages,
                temperature=self.kwargs.get("temperature", 0.3),
            )

            # Extract and print cache metadata
            cache_meta = self._extract_cache_meta(response)
            self._last_cache_meta = cache_meta
            if cache_meta is not None:
                self._print_cache_meta(cache_meta)

            content = cast(str, response.choices[0].message.content or "")
            return content.strip()
        except Exception as e:
            raise RuntimeError(f"Bailian API error: {str(e)}") from e
