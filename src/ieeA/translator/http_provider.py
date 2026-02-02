import httpx
from typing import Optional, Dict, List
from .llm_base import LLMProvider


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
        self.client = httpx.AsyncClient()

    async def translate(
        self,
        text: str,
        context: Optional[str] = None,
        glossary_hints: Optional[Dict[str, str]] = None,
        few_shot_examples: Optional[List[Dict[str, str]]] = None,
    ) -> str:
        messages = []

        # System message construction
        system_content = """你是专业的学术论文翻译专家。你的任务是将英文学术文本改写为流畅自然的中文。

## 核心规则
1. 这是"改写"任务，不是逐词翻译。目标是让中文读者能流畅阅读
2. 保持学术严谨性和专业术语准确性
3. 绝对不要修改以下内容（必须原样保留）：
   - LaTeX 命令：\\cite{...}, \\ref{...}, \\label{...}, $...$, \\textbf{...} 等
   - 占位符：[[MATH_0]], [[REF_1]], [[MACRO_2]] 等格式的标记
   - 数学公式和方程
4. 只输出翻译结果，不要添加任何解释、注释或元信息
5. 如果输入只包含占位符（如 [[MACRO_0]]），直接原样返回该占位符"""

        if context:
            system_content += f"\n\n## 上下文\n{context}"

        if glossary_hints:
            glossary_str = "\n".join([f"- {k}: {v}" for k, v in glossary_hints.items()])
            system_content += f"\n\n## 术语表\n{glossary_str}"

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

    def estimate_tokens(self, text: str) -> int:
        # Heuristic: ~2.5 chars per token
        return int(len(text) / 2.5)
