# pyright: reportPossiblyUnboundVariable=false, reportOptionalMemberAccess=false, reportMissingImports=false
from typing import Optional, Dict, List, Union
from dataclasses import dataclass

from .llm_base import LLMProvider
from .prompts import (
    FORMAT_RULES,
    CODING_CONSISTENCY_RULE,
    DEFAULT_STYLE_PROMPT,
)

anthropic = None
try:
    import anthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


@dataclass
class CacheMetrics:
    """Metrics for tracking prompt caching effectiveness."""

    cache_creation_tokens: int = 0
    cache_read_tokens: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class AnthropicCodingProvider(LLMProvider):
    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20240620",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        full_glossary=None,
        **kwargs,
    ):
        super().__init__(model, api_key, **kwargs)
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package is required for AnthropicCodingProvider. "
                "Please install it with `pip install anthropic`."
            )

        self.client = anthropic.AsyncAnthropic(api_key=api_key, base_url=base_url)
        self.message_history: List[Dict[str, str]] = []

        self._full_glossary_hints: Optional[Dict[str, str]] = None
        if full_glossary and full_glossary.terms:
            self._full_glossary_hints = {
                k: v.target for k, v in full_glossary.terms.items()
            }

        self._few_shot_examples: Optional[List[Dict[str, str]]] = None
        self._custom_system_prompt: Optional[str] = None
        self._context: Optional[str] = None

        self._cache_metrics = CacheMetrics()
        self._last_cache_hit = False

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> str:
        if few_shot_examples is not None:
            self._few_shot_examples = few_shot_examples
        if custom_system_prompt is not None:
            self._custom_system_prompt = custom_system_prompt
        if context is not None:
            self._context = context

        _ = glossary_hints

        style_prompt = (
            self._custom_system_prompt
            if self._custom_system_prompt
            else DEFAULT_STYLE_PROMPT
        )
        format_rules = FORMAT_RULES
        consistency_rule = (
            CODING_CONSISTENCY_RULE if self.kwargs.get("coding_mode", True) else ""
        )

        cache_control_marker = {"type": "ephemeral"}

        system_blocks: List[Dict[str, Union[str, Dict]]] = []

        system_blocks.append(
            {
                "type": "text",
                "text": f"{style_prompt}\n\n{format_rules}",
            }
        )

        if consistency_rule:
            system_blocks.append(
                {
                    "type": "text",
                    "text": consistency_rule,
                }
            )

        if self._full_glossary_hints:
            glossary_str = "\n".join(
                [f"- {k}: {v}" for k, v in self._full_glossary_hints.items()]
            )
            system_blocks.append(
                {
                    "type": "text",
                    "text": f"## 术语表\n请严格按照术语表翻译以下术语：\n术语表优先级高于风格偏好与上下文润色。\n{glossary_str}",
                }
            )

        if self._context:
            system_blocks.append(
                {
                    "type": "text",
                    "text": f"## 上下文\n{self._context}",
                }
            )

        system_blocks[-1]["cache_control"] = cache_control_marker

        messages: List[Dict[str, str]] = []
        if self._few_shot_examples:
            for ex in self._few_shot_examples:
                messages.append({"role": "user", "content": ex.get("source", "")})
                messages.append({"role": "assistant", "content": ex.get("target", "")})

        messages.extend(self.message_history)
        messages.append({"role": "user", "content": text})

        try:
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.kwargs.get("max_tokens", 4096),
                system=system_blocks,
                messages=messages,
                temperature=self.kwargs.get("temperature", 0.3),
            )

            if hasattr(response, "usage") and response.usage:
                usage = response.usage
                self._cache_metrics.input_tokens = (
                    getattr(usage, "input_tokens", 0) or 0
                )
                self._cache_metrics.output_tokens = (
                    getattr(usage, "output_tokens", 0) or 0
                )
                self._cache_metrics.cache_creation_tokens = (
                    getattr(usage, "cache_creation_input_tokens", 0) or 0
                )
                self._cache_metrics.cache_read_tokens = (
                    getattr(usage, "cache_read_input_tokens", 0) or 0
                )
                self._last_cache_hit = self._cache_metrics.cache_read_tokens > 0

            full_text = []
            for block in response.content:
                if block.type == "text":
                    full_text.append(block.text)
            result = "".join(full_text).strip()
        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {str(e)}") from e

        self.message_history.append({"role": "user", "content": text})
        self.message_history.append({"role": "assistant", "content": result})

        return result

    async def ping(self) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hi"}],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()

    def estimate_tokens(self, text: str) -> int:
        return int(len(text) / 3.5)

    def get_history(self) -> List[Dict[str, str]]:
        return list(self.message_history)

    def set_history(self, history: List[Dict[str, str]]) -> None:
        self.message_history = list(history)

    def get_cache_metrics(self) -> CacheMetrics:
        return self._cache_metrics

    def last_request_used_cache(self) -> bool:
        return self._last_cache_hit
