# pyright: reportPossiblyUnboundVariable=false, reportOptionalMemberAccess=false
"""Stateful OpenAI provider that accumulates message history for KV cache optimization."""

from typing import Optional, Dict, List, Any, cast
from .llm_base import LLMProvider
from .prompts import build_system_prompt

openai = None
try:
    import openai

    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

tiktoken: Any | None = None
try:
    import tiktoken as _tiktoken

    tiktoken = _tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


class OpenAICodingProvider(LLMProvider):
    """Stateful translation provider that accumulates message history.

    Messages are assembled as:
        system(fixed) + few-shot(always) + history(append-only) + current_user(new)

    This ordering ensures the prefix never changes between requests,
    enabling KV cache reuse on the API side.
    """

    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        full_glossary=None,
        **kwargs,
    ):
        super().__init__(model, api_key, **kwargs)
        if not HAS_OPENAI or openai is None:
            raise ImportError(
                "openai package is required for OpenAICodingProvider. "
                "Please install it with `pip install openai`."
            )

        timeout_config = openai.Timeout(
            connect=60.0,
            read=300.0,
            write=60.0,
            pool=60.0,
        )
        self.client = openai.AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=timeout_config,
        )

        # Stateful history: accumulated user/assistant pairs
        self.message_history: List[Dict[str, str]] = []

        # Extract full glossary hints for fixed system prompt
        self._full_glossary_hints: Optional[Dict[str, str]] = None
        if full_glossary and full_glossary.terms:
            self._full_glossary_hints = {
                k: v.target for k, v in full_glossary.terms.items()
            }

        # Cache first-call params for subsequent calls
        self._few_shot_examples: Optional[List[Dict[str, str]]] = None
        self._custom_system_prompt: Optional[str] = None
        self._context: Optional[str] = None

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> str:
        # Cache first-call params for subsequent calls
        if few_shot_examples is not None:
            self._few_shot_examples = few_shot_examples
        if custom_system_prompt is not None:
            self._custom_system_prompt = custom_system_prompt
        if context is not None:
            self._context = context

        # 1. Build FIXED system prompt (full glossary, coding_mode=True)
        #    glossary_hints param is intentionally ignored — we use self._full_glossary_hints
        system_content = build_system_prompt(
            glossary_hints=self._full_glossary_hints,
            context=self._context,
            custom_system_prompt=self._custom_system_prompt,
            coding_mode=True,
        )

        # 2. Assemble messages: system + few-shot + history + current
        messages: List[Dict[str, str]] = [{"role": "system", "content": system_content}]

        # Few-shot (ALWAYS injected, every request)
        if self._few_shot_examples:
            for ex in self._few_shot_examples:
                messages.append({"role": "user", "content": ex.get("source", "")})
                messages.append({"role": "assistant", "content": ex.get("target", "")})

        # History (accumulated, append-only)
        messages.extend(self.message_history)

        # Current user message
        messages.append({"role": "user", "content": text})

        # 3. Call API
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.kwargs.get("temperature", 0.3),
            )
            content = cast(str, response.choices[0].message.content or "")
            result = content.strip()
        except Exception as e:
            # API failed — DO NOT modify history (retry-safe)
            raise RuntimeError(f"OpenAI API error: {str(e)}") from e

        # 4. SUCCESS ONLY: append to history
        self.message_history.append({"role": "user", "content": text})
        self.message_history.append({"role": "assistant", "content": result})

        return result

    async def ping(self) -> str:
        """Ping the API without modifying message_history."""
        response = await self.client.chat.completions.create(
            model=self.model,
            messages=[{"role": "user", "content": "Say hi"}],
            max_tokens=10,
        )
        return cast(str, response.choices[0].message.content or "")

    def estimate_tokens(self, text: str) -> int:
        if HAS_TIKTOKEN and tiktoken is not None:
            try:
                encoding = tiktoken.encoding_for_model(self.model)
                return len(encoding.encode(text))
            except KeyError:
                # Fallback for unknown models
                encoding = tiktoken.get_encoding("cl100k_base")
                return len(encoding.encode(text))
        else:
            # Rough estimation if tiktoken is not available
            return int(len(text) / 2.5)

    def get_history(self) -> List[Dict[str, str]]:
        """Return a copy of the accumulated message history."""
        return list(self.message_history)

    def set_history(self, history: List[Dict[str, str]]) -> None:
        """Replace message history (e.g. for checkpoint restore)."""
        self.message_history = list(history)
