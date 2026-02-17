"""Volcano Engine Ark provider with context API caching."""

import datetime
from typing import Optional, Dict, List, Any

from .llm_base import LLMProvider
from .prompts import build_system_prompt

_Ark = None
try:
    from volcenginesdkarkruntime import Ark as _ArkClass

    _Ark = _ArkClass
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
        if not HAS_ARK or _Ark is None:
            raise ImportError(
                "volcenginesdkarkruntime is required for ArkProvider. "
                "Install with: pip install 'volcengine-python-sdk[ark]'"
            )

        client_kwargs: Dict[str, Any] = {}
        if api_key:
            client_kwargs["api_key"] = api_key
        if base_url:
            client_kwargs["base_url"] = base_url

        self.client = _Ark(**client_kwargs)
        self._context_id: Optional[str] = None
        self._prebuilt_system_prompt: Optional[str] = None
        self._prebuilt_batch_prompt: Optional[str] = None

    def setup_context(self, system_prompt: Optional[str] = None) -> None:
        """Create a cached context with the system prompt.

        Args:
            system_prompt: The system prompt to cache. If None, uses _prebuilt_system_prompt.
        """
        prompt = system_prompt or self._prebuilt_system_prompt
        if not prompt:
            return

        context = self.client.context.create(
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
                    response = self.client.context.completions.create(
                        context_id=self._context_id,
                        model=self.model,
                        messages=messages,
                        temperature=self.kwargs.get("temperature", 0.3),
                    )
                except Exception:
                    # Context may have expired (TTL), rebuild and retry
                    self.setup_context()
                    if self._context_id:
                        response = self.client.context.completions.create(
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
                        response = self.client.chat.completions.create(
                            model=self.model,
                            messages=messages,
                            temperature=self.kwargs.get("temperature", 0.3),
                        )
            else:
                # Standard API call (no context caching)
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    temperature=self.kwargs.get("temperature", 0.3),
                )

            content = response.choices[0].message.content or ""
            return content.strip()
        except Exception as e:
            raise RuntimeError(f"Ark API error: {str(e)}") from e

    async def ping(self) -> str:
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": "Say hi"}],
            max_tokens=10,
        )
        return (response.choices[0].message.content or "").strip()

    def estimate_tokens(self, text: str) -> int:
        # Heuristic: mixed CJK/English ~2.5 chars per token
        return int(len(text) / 2.5)
