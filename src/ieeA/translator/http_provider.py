import httpx
from typing import Optional, Dict, List
from .llm_base import LLMProvider
from .prompts import build_system_prompt


class DirectHTTPProvider(LLMProvider):
    """Direct HTTP provider for OpenAI-compatible endpoints."""

    def __init__(
        self,
        model: str,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        **kwargs,
    ):
        super().__init__(model, api_key, **kwargs)
        if endpoint is None:
            raise ValueError("endpoint is required for DirectHTTPProvider")
        self.endpoint = endpoint
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=60.0, read=300.0, write=60.0, pool=60.0)
        )
        self._prebuilt_system_prompt: Optional[str] = None
        self._prebuilt_batch_prompt: Optional[str] = None

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
        custom_system_prompt: Optional[str] = None,
    ) -> str:
        messages = []

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

        # Prepare request
        headers = {
            "Content-Type": "application/json",
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        request_body = {
            "model": self.model,
            "messages": messages,
            "temperature": self.kwargs.get("temperature", 0.3),
        }

        try:
            response = await self.client.post(
                self.endpoint,
                json=request_body,
                headers=headers,
            )
            response.raise_for_status()
            data = response.json()
            content = data["choices"][0]["message"]["content"]
            return content.strip()
        except Exception as e:
            raise RuntimeError(f"HTTP API error: {str(e)}") from e

    async def ping(self) -> str:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        request_body = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Say hi"}],
            "max_tokens": 10,
        }
        response = await self.client.post(
            self.endpoint, json=request_body, headers=headers
        )
        response.raise_for_status()
        return response.json()["choices"][0]["message"]["content"].strip()

    def estimate_tokens(self, text: str) -> int:
        # Heuristic: ~2.5 chars per token
        return int(len(text) / 2.5)
