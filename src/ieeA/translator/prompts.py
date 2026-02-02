"""Prompt templates for translation pipeline."""

from typing import Optional, Dict, List


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
