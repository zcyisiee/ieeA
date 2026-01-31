import os
import asyncio
from typing import Optional, Dict, List, Any
from .llm_base import LLMProvider

try:
    import dashscope
    from http import HTTPStatus
    HAS_DASHSCOPE = True
except ImportError:
    HAS_DASHSCOPE = False

class QwenProvider(LLMProvider):
    def __init__(self, model: str = "qwen-max", api_key: Optional[str] = None, **kwargs):
        super().__init__(model, api_key, **kwargs)
        if not HAS_DASHSCOPE:
            raise ImportError("dashscope package is required for QwenProvider. Please install it with `pip install dashscope`.")
        
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        if not self.api_key:
            raise ValueError("DASHSCOPE_API_KEY is required for QwenProvider")
        
        dashscope.api_key = self.api_key

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

        # Wrap synchronous dashscope call in a thread
        def _call_dashscope():
            return dashscope.Generation.call(
                model=self.model,
                messages=messages,
                result_format='message',
                temperature=self.kwargs.get("temperature", 0.3),
            )

        try:
            response = await asyncio.to_thread(_call_dashscope)
            
            if response.status_code == HTTPStatus.OK:
                return response.output.choices[0].message.content.strip()
            else:
                raise RuntimeError(f"DashScope API error: {response.code} - {response.message}")
                
        except Exception as e:
            raise RuntimeError(f"Qwen API error: {str(e)}") from e

    def estimate_tokens(self, text: str) -> int:
        # Qwen tokenization is roughly similar to other models but uses a different tokenizer.
        # DashScope has a tokenizer API but it requires network calls or local library.
        # Simple heuristic for now: ~2.5 chars/token
        return int(len(text) / 2.5)
