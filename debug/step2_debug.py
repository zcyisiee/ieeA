#!/usr/bin/env python3
"""Debug Step 2: 保护数学环境、行内公式、命令"""

import sys
import re
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

DEBUG_DIR = Path(__file__).parent


class DebugParserStep2:
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

    def __init__(self):
        self.protected_counter = 0
        self.placeholder_map = {}

    def _replace_with_placeholder(
        self, text: str, pattern: re.Pattern, prefix: str
    ) -> str:
        def replacer(match):
            matched_text = match.group(0)
            if "{{CHUNK_" in matched_text:
                return matched_text
            self.protected_counter += 1
            placeholder = f"[[{prefix}_{self.protected_counter}]]"
            self.placeholder_map[placeholder] = matched_text
            return placeholder

        return pattern.sub(replacer, text)

    def _protect_math_environments(self, text: str) -> str:
        for env in self.PROTECTED_ENVIRONMENTS:
            pattern = re.compile(
                r"(\\begin\{"
                + re.escape(env)
                + r"\}.*?\\end\{"
                + re.escape(env)
                + r"\})",
                re.DOTALL,
            )
            text = self._replace_with_placeholder(text, pattern, "MATHENV")
        return text

    def _protect_inline_math(self, text: str) -> str:
        pattern = re.compile(r"(\$\$.*?\$\$|\$[^$]+?\$)", re.DOTALL)
        text = self._replace_with_placeholder(text, pattern, "MATH")
        pattern = re.compile(r"(\\\[.*?\\\]|\\\(.*?\\\))", re.DOTALL)
        text = self._replace_with_placeholder(text, pattern, "MATH")
        return text

    def _protect_commands(self, text: str) -> str:
        patterns = [
            (r"(\\cite\{[^}]*\})", "CITE"),
            (r"(\\citep?\{[^}]*\})", "CITE"),
            (r"(\\ref\{[^}]*\})", "REF"),
            (r"(\\eqref\{[^}]*\})", "REF"),
            (r"(\\label\{[^}]*\})", "LABEL"),
            (r"(\\url\{[^}]*\})", "URL"),
            (r"(\\href\{[^}]*\}\{[^}]*\})", "HREF"),
            (r"(\\footnote\{[^}]*\})", "FOOTNOTE"),
            (r"(\\includegraphics(?:\[[^\]]*\])?\{[^}]*\})", "GRAPHICS"),
        ]
        for pattern_str, prefix in patterns:
            pattern = re.compile(pattern_str)
            text = self._replace_with_placeholder(text, pattern, prefix)
        return text


def main():
    print("=== Debug Step 2: 保护数学环境/公式/命令 ===\n")

    input_file = DEBUG_DIR / "05_body_captions_extracted.tex"
    if not input_file.exists():
        print(f"ERROR: {input_file} not found. Run step1 first.")
        return

    content = input_file.read_text(encoding="utf-8")
    print(f"输入: {len(content)} 字符")

    parser = DebugParserStep2()

    print("\n--- Step 2.1: Protect Math Environments ---")
    result = parser._protect_math_environments(content)
    math_env_count = len(
        [k for k in parser.placeholder_map if k.startswith("[[MATHENV_")]
    )
    print(f"数学环境占位符: {math_env_count} 个")

    (DEBUG_DIR / "06_math_env_protected.tex").write_text(result, encoding="utf-8")

    print("\n--- Step 2.2: Protect Inline Math ---")
    result = parser._protect_inline_math(result)
    inline_math_count = len(
        [k for k in parser.placeholder_map if k.startswith("[[MATH_")]
    )
    print(f"行内公式占位符: {inline_math_count} 个")

    (DEBUG_DIR / "07_inline_math_protected.tex").write_text(result, encoding="utf-8")

    print("\n--- Step 2.3: Protect Commands ---")
    result = parser._protect_commands(result)

    cmd_stats = {}
    for k in parser.placeholder_map:
        prefix = k.split("_")[0][2:]
        cmd_stats[prefix] = cmd_stats.get(prefix, 0) + 1

    print("命令占位符统计:")
    for prefix, count in sorted(cmd_stats.items()):
        print(f"  {prefix}: {count}")

    (DEBUG_DIR / "08_commands_protected.tex").write_text(result, encoding="utf-8")
    print(f"\n保存: debug/08_commands_protected.tex")

    print(f"\n总占位符数: {len(parser.placeholder_map)}")

    (DEBUG_DIR / "08_placeholder_map.json").write_text(
        json.dumps(
            {
                k: v[:200] + "..." if len(v) > 200 else v
                for k, v in parser.placeholder_map.items()
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"保存: debug/08_placeholder_map.json")

    print("\n=== 检查 Overall Algorithm 和 Conclusion 是否存在 ===")
    if "Overall Algorithm" in result:
        print("✓ 'Overall Algorithm' 存在于输出中")
    else:
        print("✗ 'Overall Algorithm' 不在输出中!")
        if "Overall Algorithm" in content:
            print("  但它在输入中存在 - 可能被误保护")

    if "Conclusion" in result:
        print("✓ 'Conclusion' 存在于输出中")
    else:
        print("✗ 'Conclusion' 不在输出中!")

    print("\n=== Step 2 完成 ===")


if __name__ == "__main__":
    main()
