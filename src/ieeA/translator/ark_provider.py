"""Volcano Engine Ark provider with context API caching."""

import asyncio
import datetime
import json
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
        self._context_ids: Dict[str, str] = {}
        self._context_prefix_keys: Dict[str, str] = {}
        self._context_setup_locks: Dict[str, asyncio.Lock] = {}
        self._prebuilt_system_prompt: Optional[str] = None
        self._prebuilt_batch_prompt: Optional[str] = None

    @staticmethod
    def _get_field(obj: Any, key: str, default: Any = None) -> Any:
        if obj is None:
            return default
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    def _ensure_context_state(self) -> None:
        if not hasattr(self, "_context_ids") or self._context_ids is None:  # type: ignore[attr-defined]
            self._context_ids = {}
        if not hasattr(self, "_context_prefix_keys") or self._context_prefix_keys is None:  # type: ignore[attr-defined]
            self._context_prefix_keys = {}
        if (
            not hasattr(self, "_context_setup_locks")
            or self._context_setup_locks is None  # type: ignore[attr-defined]
        ):
            self._context_setup_locks = {}

        legacy_context_id = getattr(self, "_context_id", None)
        if legacy_context_id and "individual" not in self._context_ids:
            self._context_ids["individual"] = legacy_context_id

    def _get_context_id_for_variant(self, prompt_variant: str) -> Optional[str]:
        self._ensure_context_state()
        return self._context_ids.get(prompt_variant)

    def _set_context_id_for_variant(
        self,
        prompt_variant: str,
        context_id: str,
        prefix_key: Optional[str] = None,
    ) -> None:
        self._ensure_context_state()
        self._context_ids[prompt_variant] = context_id
        if prefix_key is not None:
            self._context_prefix_keys[prompt_variant] = prefix_key
        if prompt_variant == "individual":
            self._context_id = context_id

    def _get_context_lock(self, prompt_variant: str) -> asyncio.Lock:
        self._ensure_context_state()
        lock = self._context_setup_locks.get(prompt_variant)
        if lock is None:
            lock = asyncio.Lock()
            self._context_setup_locks[prompt_variant] = lock
        return lock

    @staticmethod
    def _build_few_shot_messages(
        few_shot_examples: Optional[List[Dict[str, str]]],
    ) -> List[Dict[str, str]]:
        messages: List[Dict[str, str]] = []
        if few_shot_examples:
            for example in few_shot_examples:
                messages.append({"role": "user", "content": example.get("source", "")})
                messages.append(
                    {"role": "assistant", "content": example.get("target", "")}
                )
        return messages

    @staticmethod
    def _build_prefix_key(messages: List[Dict[str, str]]) -> str:
        return json.dumps(messages, ensure_ascii=False, sort_keys=True)

    def _build_context_prefix_messages(
        self,
        prompt_variant: str,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        system_prompt: Optional[str] = None,
    ) -> List[Dict[str, str]]:
        prompt = system_prompt or self._get_prebuilt_prompt(prompt_variant)
        if not prompt:
            return []
        messages: List[Dict[str, str]] = [{"role": "system", "content": prompt}]
        messages.extend(self._build_few_shot_messages(few_shot_examples))
        return messages

    def _extract_cache_meta(
        self,
        response: Any,
        use_context: bool,
        prompt_variant: str,
        context_id: Optional[str],
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
            "variant": prompt_variant,
            "context_id": context_id,
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
            f"variant={cache_meta.get('variant')} "
            f"mode={cache_meta.get('mode')} "
            f"hit={cache_meta.get('cache_hit')} "
            f"cached_tokens={cache_meta.get('cached_tokens')} "
            f"prompt_tokens={cache_meta.get('prompt_tokens')} "
            f"completion_tokens={cache_meta.get('completion_tokens')} "
            f"total_tokens={cache_meta.get('total_tokens')} "
            f"context_id={cache_meta.get('context_id')}"
        )

    async def setup_context(
        self,
        system_prompt: Optional[str] = None,
        *,
        prompt_variant: str = "individual",
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        """Create a cached context with the stable prefix (system + few-shot).

        Args:
            system_prompt: The system prompt to cache. If None, uses prebuilt prompt for variant.
            prompt_variant: Prefix variant name ("individual" or "batch").
            few_shot_examples: Few-shot examples to include in the cached prefix.
        """
        self._ensure_context_state()
        prefix_messages = self._build_context_prefix_messages(
            prompt_variant=prompt_variant,
            few_shot_examples=few_shot_examples,
            system_prompt=system_prompt,
        )
        if not prefix_messages:
            return

        prefix_key = self._build_prefix_key(prefix_messages)
        async with self._get_context_lock(prompt_variant):
            current_context_id = self._context_ids.get(prompt_variant)
            current_prefix_key = self._context_prefix_keys.get(prompt_variant)
            if current_context_id and current_prefix_key == prefix_key:
                return

            context = await self.client.context.create(
                model=self.model,
                mode="common_prefix",
                messages=prefix_messages,
                ttl=datetime.timedelta(minutes=5),
            )
            self._set_context_id_for_variant(
                prompt_variant=prompt_variant,
                context_id=context.id,
                prefix_key=prefix_key,
            )

    async def prepare_prompt_cache_variants(
        self,
        prompt_variants: List[str],
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> None:
        for prompt_variant in prompt_variants:
            try:
                await self.setup_context(
                    prompt_variant=prompt_variant,
                    few_shot_examples=few_shot_examples,
                )
            except Exception as e:
                print(
                    "[ARK CACHE] "
                    f"variant={prompt_variant} "
                    "mode=chat "
                    f"warmup_failed=True reason={e}"
                )

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
        prompt_variant: str = "individual",
    ) -> str:
        self._ensure_context_state()
        few_shot_messages = self._build_few_shot_messages(few_shot_examples)
        selected_prebuilt_prompt = self._get_prebuilt_prompt(prompt_variant)
        current_context_id = self._get_context_id_for_variant(prompt_variant)

        user_message = {"role": "user", "content": text}

        # Determine if we use context API (pre-built prompt) or standard path
        use_context = (
            selected_prebuilt_prompt is not None
            and glossary_hints is None
            and current_context_id is not None
        )

        context_messages: List[Dict[str, str]] = [user_message]
        chat_messages: Optional[List[Dict[str, str]]] = None

        try:
            used_context = False
            if use_context:
                # Use context API for cached system prompt
                try:
                    response = await self.client.context.completions.create(
                        context_id=current_context_id,
                        model=self.model,
                        messages=context_messages,
                        temperature=self.kwargs.get("temperature", 0.3),
                    )
                    used_context = True
                except Exception:
                    # Context may have expired (TTL), rebuild and retry
                    try:
                        await self.setup_context(
                            prompt_variant=prompt_variant,
                            few_shot_examples=few_shot_examples,
                        )
                    except Exception as warmup_error:
                        print(
                            "[ARK CACHE] "
                            f"variant={prompt_variant} "
                            "mode=chat "
                            "warmup_failed=True "
                            f"reason={warmup_error}"
                        )

                    current_context_id = self._get_context_id_for_variant(prompt_variant)
                    if current_context_id:
                        response = await self.client.context.completions.create(
                            context_id=current_context_id,
                            model=self.model,
                            messages=context_messages,
                            temperature=self.kwargs.get("temperature", 0.3),
                        )
                        used_context = True
                    else:
                        # Fallback to standard call
                        if selected_prebuilt_prompt is not None and glossary_hints is None:
                            system_content = selected_prebuilt_prompt
                        else:
                            system_content = build_system_prompt(
                                glossary_hints=glossary_hints,
                                context=context,
                                few_shot_examples=few_shot_examples,
                                custom_system_prompt=custom_system_prompt,
                            )
                        chat_messages = [{"role": "system", "content": system_content}]
                        chat_messages.extend(few_shot_messages)
                        chat_messages.append(user_message)
                        response = await self.client.chat.completions.create(
                            model=self.model,
                            messages=chat_messages,
                            temperature=self.kwargs.get("temperature", 0.3),
                        )
            else:
                # Standard API call (no context caching)
                if selected_prebuilt_prompt is not None and glossary_hints is None:
                    system_content = selected_prebuilt_prompt
                else:
                    system_content = build_system_prompt(
                        glossary_hints=glossary_hints,
                        context=context,
                        few_shot_examples=few_shot_examples,
                        custom_system_prompt=custom_system_prompt,
                    )
                chat_messages = [{"role": "system", "content": system_content}]
                chat_messages.extend(few_shot_messages)
                chat_messages.append(user_message)
                response = await self.client.chat.completions.create(
                    model=self.model,
                    messages=chat_messages,
                    temperature=self.kwargs.get("temperature", 0.3),
                )

            active_context_id = (
                self._get_context_id_for_variant(prompt_variant) if used_context else None
            )
            cache_meta = self._extract_cache_meta(
                response=response,
                use_context=used_context,
                prompt_variant=prompt_variant,
                context_id=active_context_id,
            )
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
