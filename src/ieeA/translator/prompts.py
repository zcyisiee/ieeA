"""Prompt templates for translation pipeline."""

from typing import Optional, Dict, List


# ============================================================================
# 硬编码格式规则 - 用户不可修改
# 这些规则确保 LaTeX 命令和占位符在翻译过程中被正确保留
# ============================================================================
FORMAT_RULES = """## 格式规则
以下内容必须原样保留，绝对不要修改：
- LaTeX 命令：\\cite{...}, \\ref{...}, \\label{...}, $...$, \\textbf{...} 等
- 占位符：[[MATH_0]], [[REF_1]], [[MACRO_2]] 等格式的标记
- 数学公式和方程

输出要求：
- 只输出翻译结果，不要添加任何解释、注释或元信息
- 如果输入只包含占位符（如 [[MACRO_0]]），直接原样返回该占位符"""


# ============================================================================
# 默认翻译风格提示词 - 用户可通过 config.yaml 的 custom_system_prompt 替换
# ============================================================================
DEFAULT_STYLE_PROMPT = """你是专业的学术论文翻译专家。你的任务是将英文学术文本改写为流畅自然的中文。

翻译原则：
1. 这是"改写"任务，不是逐词翻译。目标是让中文读者能流畅阅读
2. 保持学术严谨性和专业术语准确性"""


def build_system_prompt(
    glossary_hints: Optional[Dict[str, str]] = None,
    context: Optional[str] = None,
    few_shot_examples: Optional[List[Dict[str, str]]] = None,
    custom_system_prompt: Optional[str] = None,
    language: str = "zh",
) -> str:
    """Build unified system prompt for all providers.

    提示词组装顺序：
    1. 用户自定义提示词 或 默认翻译风格提示词
    2. 硬编码格式规则 (不可修改)
    3. 术语表 (如有)
    4. 上下文 (如有)

    Args:
        glossary_hints: Optional glossary mapping (source: target)
        context: Optional context information
        few_shot_examples: Optional few-shot examples (not used in system prompt)
        custom_system_prompt: Optional custom style prompt to replace default
        language: Target language code (default: "zh" for Chinese)

    Returns:
        Formatted system prompt string
    """
    # 1. 使用用户自定义提示词或默认风格提示词
    style_prompt = (
        custom_system_prompt if custom_system_prompt else DEFAULT_STYLE_PROMPT
    )

    # 2. 组装：风格提示词 + 硬编码格式规则
    system_content = f"{style_prompt}\n\n{FORMAT_RULES}"

    # 3. 添加术语表（如有）
    if glossary_hints:
        glossary_str = "\n".join([f"- {k}: {v}" for k, v in glossary_hints.items()])
        system_content += f"\n\n## 术语表\n{glossary_str}"

    # 4. 添加上下文（如有）
    if context:
        system_content += f"\n\n## 上下文\n{context}"

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
