#!/usr/bin/env python3
"""测试修复后的完整流程"""

import re
import json
from pathlib import Path

DEBUG_DIR = Path(__file__).parent

PROTECTED_ENVIRONMENTS = {
    "equation",
    "align",
    "gather",
    "split",
    "eqnarray",
    "multline",
    "equation*",
    "align*",
    "gather*",
    "eqnarray*",
    "multline*",
    "tikzpicture",
    "lstlisting",
    "verbatim",
    "minted",
    "algorithm",
    "algorithm2e",
    "algorithmic",
}

placeholder_map = {}
counter = 0


def replace_with_placeholder(text, pattern, prefix):
    global counter

    def replacer(match):
        global counter
        matched_text = match.group(0)
        if "{{CHUNK_" in matched_text:
            return matched_text
        counter += 1
        placeholder = f"[[{prefix}_{counter}]]"
        placeholder_map[placeholder] = matched_text
        return placeholder

    return pattern.sub(replacer, text)


def main():
    content = (DEBUG_DIR / "05_body_captions_extracted.tex").read_text(encoding="utf-8")
    print(f"输入: {len(content)} 字符")

    print("\n--- Step 1: 保护数学环境 (含 algorithm) ---")
    for env in PROTECTED_ENVIRONMENTS:
        pattern = re.compile(
            r"(\\begin\{" + re.escape(env) + r"\}.*?\\end\{" + re.escape(env) + r"\})",
            re.DOTALL,
        )
        content = replace_with_placeholder(content, pattern, "MATHENV")

    math_env_count = len([k for k in placeholder_map if k.startswith("[[MATHENV_")])
    print(f"数学环境占位符: {math_env_count} 个")

    (DEBUG_DIR / "06_fixed_math_env.tex").write_text(content, encoding="utf-8")

    print("\n--- Step 2: 保护行内公式 ---")
    pattern = re.compile(r"(\$\$.*?\$\$|\$[^$]+?\$)", re.DOTALL)
    content = replace_with_placeholder(content, pattern, "MATH")

    inline_math_count = len([k for k in placeholder_map if k.startswith("[[MATH_")])
    print(f"行内公式占位符: {inline_math_count} 个")

    (DEBUG_DIR / "07_fixed_inline_math.tex").write_text(content, encoding="utf-8")

    print("\n=== 检查关键内容 ===")
    if "Overall Algorithm" in content:
        print("✓ Overall Algorithm 存在")
    else:
        print("✗ Overall Algorithm 丢失!")
        for k, v in placeholder_map.items():
            if "Overall Algorithm" in v:
                print(f"  被吞进: {k} (长度 {len(v)})")
                break

    if "Conclusion" in content:
        print("✓ Conclusion 存在")
    else:
        print("✗ Conclusion 丢失!")

    (DEBUG_DIR / "09_fixed_protected.tex").write_text(content, encoding="utf-8")
    print("\n保存: debug/09_fixed_protected.tex")


if __name__ == "__main__":
    main()
