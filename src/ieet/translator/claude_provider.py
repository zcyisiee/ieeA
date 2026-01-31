import os
from typing import Optional, Dict, List, Any
from .llm_base import LLMProvider

try:
    from anthropic import AsyncAnthropic
    HAS_ANTHROPIC = True
except ImportError:
    HAS_ANTHROPIC = False

class ClaudeProvider(LLMProvider):
    def __init__(self, model: str = "claude-3-5-sonnet-20240620", api_key: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, **kwargs)
        if not HAS_ANTHROPIC:
            raise ImportError("anthropic package is required for ClaudeProvider. Please install it with `pip install anthropic`.")
        
        self.client = AsyncAnthropic(api_key=api_key or os.getenv("ANTHROPIC_API_KEY"))

    async def translate(
        self, 
        text: str, 
        context: Optional[str] = None, 
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None
    ) -> str:
        # System message construction
        system_content = "You are a professional academic translator. Translate the following text into fluent Chinese."
        if context:
            system_content += f"\nContext: {context}"
        
        if glossary_hints:
            glossary_str = "\n".join([f"{k}: {v}" for k, v in glossary_hints.items()])
            system_content += f"\nGlossary Hints:\n{glossary_str}"

        messages = []

        # Few-shot examples
        if few_shot_examples:
            for example in few_shot_examples:
                messages.append({"role": "user", "content": example.get("source", "")})
                messages.append({"role": "assistant", "content": example.get("target", "")})

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
                if block.type == 'text':
                    full_text.append(block.text)
            
            return "".join(full_text).strip()
        except Exception as e:
            raise RuntimeError(f"Claude API error: {str(e)}") from e

    def estimate_tokens(self, text: str) -> int:
        # Anthropic doesn't expose a simple local tokenizer in the SDK for estimation easily without calling API or using third party.
        # Simple heuristic: ~3.5 chars per token for English.
        return int(len(text) / 3.5)
