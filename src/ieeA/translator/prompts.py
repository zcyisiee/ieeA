"""Prompt templates for translation pipeline."""

from typing import Optional, Dict, List


CORE_TRANSLATION_RULES = """你是专业的学术论文翻译专家。你的任务是将英文学术文本改写为流畅自然的中文。

## 核心规则
1. 这是"改写"任务，不是逐词翻译。目标是让中文读者能流畅阅读
2. 保持学术严谨性和专业术语准确性
3. 绝对不要修改以下内容（必须原样保留）：
   - LaTeX 命令：\\cite{...}, \\ref{...}, \\label{...}, $...$, \\textbf{...} 等
   - 占位符：[[MATH_0]], [[REF_1]], [[MACRO_2]] 等格式的标记
   - 数学公式和方程
4. 只输出翻译结果，不要添加任何解释、注释或元信息
5. 如果输入只包含占位符（如 [[MACRO_0]]），直接原样返回该占位符"""


TRANSLATION_SYSTEM_PROMPT = """你是一位专业的学术论文翻译专家。请将以下英文学术文本翻译成中文。

翻译要求：
1. 采用意译/改写风格，保证中文表达自然流畅
2. 保持所有 LaTeX 命令不变（如 \\cite{}, \\ref{}, $...$）
3. 保持所有占位符不变（如 {{GLOSS_001}}）
4. 专业术语遵循以下对照表"""


def build_translation_prompt(
    content: str,
    context: Optional[str] = None,
    glossary_hints: Optional[Dict[str, str]] = None,
    few_shot_examples: Optional[List[Dict[str, str]]] = None,
    custom_system_prompt: Optional[str] = None,
) -> str:
    system_prompt = (
        custom_system_prompt if custom_system_prompt else TRANSLATION_SYSTEM_PROMPT
    )
    parts = [system_prompt]

    # Add glossary hints
    if glossary_hints:
        glossary_lines = [f"  - {src}: {tgt}" for src, tgt in glossary_hints.items()]
        parts.append("：\n" + "\n".join(glossary_lines))
    else:
        parts.append("（无特定术语表）")

    # Add context
    if context:
        parts.append(f"\n\n上下文信息：\n{context}")

    # Add few-shot examples
    if few_shot_examples:
        parts.append("\n\n参考示例：")
        for i, example in enumerate(few_shot_examples, 1):
            source = example.get("source", "")
            target = example.get("target", "")
            parts.append(f"\n示例 {i}:")
            parts.append(f"原文：{source}")
            parts.append(f"译文：{target}")

    # Add the content to translate
    parts.append(f"\n\n待翻译文本：\n{content}")
    parts.append("\n\n翻译结果：")

    return "\n".join(parts)


def build_system_message(
    glossary_hints: Optional[Dict[str, str]] = None,
    custom_system_prompt: Optional[str] = None,
) -> str:
    system_prompt = (
        custom_system_prompt if custom_system_prompt else TRANSLATION_SYSTEM_PROMPT
    )
    parts = [system_prompt]

    if glossary_hints:
        glossary_lines = [f"  - {src}: {tgt}" for src, tgt in glossary_hints.items()]
        parts.append("：\n" + "\n".join(glossary_lines))
    else:
        parts.append("（无特定术语表）")

    return "\n".join(parts)


def build_system_prompt(
    glossary_hints: Optional[Dict[str, str]] = None,
    context: Optional[str] = None,
    few_shot_examples: Optional[List[Dict[str, str]]] = None,
    language: str = "zh",
) -> str:
    """Build unified system prompt for all providers.

    Args:
        glossary_hints: Optional glossary mapping (source: target)
        context: Optional context information
        few_shot_examples: Optional few-shot examples (not used in system prompt)
        language: Target language code (default: "zh" for Chinese)

    Returns:
        Formatted system prompt string
    """
    system_content = CORE_TRANSLATION_RULES

    if context:
        system_content += f"\n\n## 上下文\n{context}"

    if glossary_hints:
        glossary_str = "\n".join([f"- {k}: {v}" for k, v in glossary_hints.items()])
        system_content += f"\n\n## 术语表\n{glossary_str}"

    return system_content


def build_batch_translation_text(chunks: List[Dict[str, str]]) -> str:
    """Build batch translation input text with numbered format.

    Args:
        chunks: List of chunks with 'chunk_id' and 'content' keys.

    Returns:
        Formatted text like:
        [1] First content
        [2] Second content
        [3] Third content
    """
    lines = []
    for idx, chunk in enumerate(chunks, 1):
        lines.append(f"[{idx}] {chunk['content']}")
    return "\n".join(lines)
