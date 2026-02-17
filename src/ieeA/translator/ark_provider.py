"""Volcano Engine Ark provider with context API caching."""

import datetime
from typing import Optional, Dict, List, Any

from .llm_base import LLMProvider
from .prompts import build_system_prompt

_AsyncArk = None
try:
    from volcenginesdkarkruntime import AsyncArk as _AsyncArkClass

    _AsyncArk = _AsyncArkClass
    HAS_ARK = True
except ImportError:
    HAS_ARK = False


class ArkProvider(LLMProvider):
    """Volcano Engine Ark provider using context API for system prompt caching."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model, api_key, **kwargs)
        if not HAS_ARK or _AsyncArk is None:
            raise ImportError(
                "volcenginesdkarkruntime is required for ArkProvider. "
                "Install with: pip install 'volcengine-python-sdk[ark]'"
            )

        client_kwargs: Dict[str, Any] = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = _AsyncArk(**client_kwargs)
        self._context_id: Optional[str] = None
        self._prebuilt_system_prompt: Optional[str] = None
        self._prebuilt_batch_prompt: Optional[str] = None

    @staticmethod
    def _get_field(obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _extract_cache_meta(
        self, response: Any, use_context: bool
    ) -> Optional[Dict[str, Any]]:
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

        prompt_details = self._get_field(usage, "prompt_tokens_details", None)
        cached_tokens = _to_int(self._get_field(prompt_details, "cached_tokens", 0))

        return {
            "provider": "ark",
            "mode": "context" if use_context else "chat",
            "context_id": self._context_id,
            "cache_hit": cached_tokens > 0,
            "cached_tokens": cached_tokens,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": total_tokens,
        }

    @staticmethod
    def _print_cache_meta(cache_meta: Dict[str, Any]) -> None:
        print(
            "[ARK CACHE] "
            f"mode={cache_meta.get('mode')} "
            f"hit={cache_meta.get('cache_hit')} "
            f"cached_tokens={cache_meta.get('cached_tokens')} "
            f"prompt_tokens={cache_meta.get('prompt_tokens')} "
            f"completion_tokens={cache_meta.get('completion_tokens')} "
            f"total_tokens={cache_meta.get('total_tokens')} "
            f"context_id={cache_meta.get('context_id')}"
        )

    async def setup_context(self, system_prompt: Optional[str] = None) -> None:
        """Create a cached context with the system prompt.

        Args:
            system_prompt: The system prompt to cache. If None, uses _prebuilt_system_prompt.
        """
        prompt = system_prompt or self._prebuilt_system_prompt
        if not prompt:
            return

        context = await self.client.context.create(
            model=self.model,
            mode="common_prefix",
            messages=[{"role": "system", "content": prompt}],
            ttl=datetime.timedelta(minutes=5),
        )
        self._context_id = context.id

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> str:
        messages: List[Dict[str, str]] = []

        # Determine if we use context API (pre-built prompt) or standard path
        use_context = (
            self._prebuilt_system_prompt is not None
            and glossary_hints is None
            and self._context_id is not None
        )

        if not use_context:
            # Standard path: build system prompt and include in messages
            if self._prebuilt_system_prompt is not None and glossary_hints is None:
                system_content = self._prebuilt_system_prompt
            else:
                system_content = build_system_prompt(
                    glossary_hints=glossary_hints,
                    context=context,
                    few_shot_examples=few_shot_examples,
                    custom_system_prompt=custom_system_prompt,
                )
            messages.append({"role": "system", "content": system_content})

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
            if use_context:
                # Use context API for cached system prompt
                try:
                    response = await self.client.context.completions.create(
                        context_id=self._context_id,
                        model=self.model,
                        messages=messages,
                        temperature=self.kwargs.get("temperature", 0.3),
                    )
                except Exception:
                    # Context may have expired (TTL), rebuild and retry
                    await self.setup_context()
                    if self._context_id:
                        response = await self.client.context.completions.create(
                            context_id=self._context_id,
                            model=self.model,
                            messages=messages,
                            temperature=self.kwargs.get("temperature", 0.3),
                        )
                    else:
                        # Fallback to standard call
                        system_content = self._prebuilt_system_prompt or ""
                        messages.insert(
                            0, {"role": "system", "content": system_content}
                        )
                        response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=self.kwargs.get("temperature", 0.3),
                        )
            else:
                # Standard API call (no context caching)
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.kwargs.get("temperature", 0.3),
                )

            cache_meta = self._extract_cache_meta(response, use_context)
            self._last_cache_meta = cache_meta
            if cache_meta is not None:
                self._print_cache_meta(cache_meta)

            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            raise RuntimeError(f"Ark API error: {str(e)}") from e

    async def ping(self) -> str:
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": "Say hi"}],
            max_tokens=10,
        )
        return (response.choices[0].message.content or "").strip()

    def estimate_tokens(self, text: str) -> int:
        # Heuristic: mixed CJK/English ~2.5 chars per token
        return int(len(text) / 2.5)
