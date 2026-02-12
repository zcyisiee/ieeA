# pyright: reportPossiblyUnboundVariable=false, reportOptionalMemberAccess=false
import os
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


class OpenAIProvider(LLMProvider):
    def __init__(
        self,
        model: str = "gpt-4o",
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model, api_key, **kwargs)
        if not HAS_OPENAI or openai is None:
            raise ImportError(
                "openai package is required for OpenAIProvider. Please install it with `pip install openai`."
            )

        # Set timeout to prevent hanging on slow/unresponsive endpoints
        # Default: 60s for connect, 300s for read (long for batch translations)
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

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> str:
        messages = []

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
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.kwargs.get("temperature", 0.3),
            )
            content = cast(str, response.choices[0].message.content or "")
            return content.strip()
        except Exception as e:
            # Handle API errors gracefully
            raise RuntimeError(f"OpenAI API error: {str(e)}") from e

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
            # English: ~4 chars per token. Chinese: ~0.6 chars per token?
            # Safer mixed heuristic: len(text) / 2.5
            return int(len(text) / 2.5)
