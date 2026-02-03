import os
from typing import Optional, Dict, List, Any
from .llm_base import LLMProvider

try:
    from volcenginesdkarkruntime import AsyncArk
    HAS_ARK = True
except ImportError:
    HAS_ARK = False

class DoubaoProvider(LLMProvider):
    def __init__(self, model: str = "doubao-pro-32k", api_key: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, **kwargs)
        if not HAS_ARK:
            raise ImportError("volcenginesdkarkruntime is required for DoubaoProvider. Please install it with `pip install volcenginesdkarkruntime`.")
        
        # Ark client is compatible with OpenAI client
        self.client = AsyncArk(
            api_key=api_key or os.getenv("ARK_API_KEY"),
            base_url=kwargs.get("base_url", "https://ark.cn-beijing.volces.com/api/v3"),
            **{k: v for k, v in kwargs.items() if k != "base_url"}
        )

    async def translate(
        self, 
        text: str, 
        context: Optional[str] = None, 
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None
    ) -> str:
        messages = []
        
        # System message construction
        system_content = "You are a professional academic translator. Translate the following text into fluent Chinese."
        if context:
            system_content += f"\nContext: {context}"
        
        if glossary_hints:
            glossary_str = "\n".join([f"{k}: {v}" for k, v in glossary_hints.items()])
            system_content += f"\nGlossary Hints:\n{glossary_str}"

        messages.append({"role": "system", "content": system_content})

        # Few-shot examples
        if few_shot_examples:
            for example in few_shot_examples:
                messages.append({"role": "user", "content": example.get("source", "")})
                messages.append({"role": "assistant", "content": example.get("target", "")})

        # User message
        messages.append({"role": "user", "content": text})

        try:
            # Ark uses the same chat completion interface as OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=self.kwargs.get("temperature", 0.3),
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            raise RuntimeError(f"Doubao (Ark) API error: {str(e)}") from e

    def estimate_tokens(self, text: str) -> int:
        # Doubao token estimation
        # Rough estimation: ~2 chars/token for mixed content
        return int(len(text) / 2.0)
