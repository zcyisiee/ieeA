import os
from typing import Optional, Dict, List, Any
from .llm_base import LLMProvider
from .prompts import build_system_prompt

try:
    from anthropic import AsyncAnthropic

    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False


class AnthropicProvider(LLMProvider):
    def __init__(
        self,
        model: str = "claude-3-5-sonnet-20240620",
        api_key: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model, api_key, **kwargs)
        if not HAS_ANTHROPIC:
            raise ImportError(
                "anthropic package is required for AnthropicProvider. Please install it with `pip install anthropic`."
            )

        self.client = AsyncAnthropic(api_key=api_key)

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> str:
        system_content = build_system_prompt(
            glossary_hints=glossary_hints,
            context=context,
            few_shot_examples=few_shot_examples,
            custom_system_prompt=custom_system_prompt,
        )

        messages = []

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
            response = await self.client.messages.create(
                model=self.model,
                max_tokens=self.kwargs.get("max_tokens", 4096),
                system=system_content,
                messages=messages,
                temperature=self.kwargs.get("temperature", 0.3),
            )

            # Robustly handle content blocks
            full_text = []
            for block in response.content:
                if block.type == "text":
                    full_text.append(block.text)

            return "".join(full_text).strip()
        except Exception as e:
            raise RuntimeError(f"Anthropic API error: {str(e)}") from e

    async def ping(self) -> str:
        response = await self.client.messages.create(
            model=self.model,
            max_tokens=10,
            messages=[{"role": "user", "content": "Say hi"}],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()

    def estimate_tokens(self, text: str) -> int:
        # Anthropic doesn't expose a simple local tokenizer in the SDK for estimation easily without calling API or using third party.
        # Simple heuristic: ~3.5 chars per token for English.
        return int(len(text) / 3.5)
