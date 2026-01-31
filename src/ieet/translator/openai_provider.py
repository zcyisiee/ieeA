# pyright: reportPossiblyUnboundVariable=false, reportOptionalMemberAccess=false
import os
from typing import Optional, Dict, List, Any, cast
from .llm_base import LLMProvider

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

        self.client = openai.AsyncOpenAI(
            api_key=api_key or os.getenv("OPENAI_API_KEY"),
            base_url=base_url or os.getenv("OPENAI_BASE_URL"),
        )

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
