#!/usr/bin/env python3
"""
Debug Step 1: 执行 parser 的前两个步骤
1. flatten LaTeX (展开 \input)
2. 移除注释
3. 分离 preamble/body
4. protect_author_block
5. extract_captions

输出中间产物供检查
"""

import os
import sys
import re
import uuid
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ieeA.parser.structure import Chunk

SOURCE_FILE = Path(__file__).parent.parent / "output/2511.16709/neurips_2025.tex"
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


class DebugParser:
    """简化版 parser，用于逐步调试"""

    def __init__(self):
        self.chunks = []
        self.protected_counter = 0
        self.placeholder_map = {}

    def _flatten_latex(self, content: str, base_dir: str) -> str:
        """展开 \input 和 \include"""

        def replace_input(match):
            filename = match.group(3)
            candidates = [filename]
            if not filename.lower().endswith(".tex"):
                candidates.append(filename + ".tex")

            for cand in candidates:
                path = os.path.join(base_dir, cand)
                if os.path.exists(path):
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            sub_content = f.read()
                        sub_dir = os.path.dirname(path)
                        return self._flatten_latex(sub_content, sub_dir)
                    except Exception as e:
                        print(f"Warning: Could not read {path}: {e}")
                        return match.group(0)

            print(f"Warning: File not found: {filename} in {base_dir}")
            return match.group(0)

        pattern = re.compile(r"(^|[^%])\\(input|include)\{([^}]+)\}")
        return pattern.sub(replace_input, content)

    def _remove_comments(self, content: str) -> str:
        """移除 LaTeX 注释"""
        lines = content.split("\n")
        result = []
        in_verbatim = False
        verbatim_envs = {"verbatim", "lstlisting", "minted", "comment"}

        for line in lines:
            for env in verbatim_envs:
                if f"\\begin{{{env}}}" in line:
                    in_verbatim = True
                if f"\\end{{{env}}}" in line:
                    in_verbatim = False

            if in_verbatim:
                result.append(line)
                continue

            stripped = line.lstrip()
            if stripped.startswith("%!"):
                result.append(line)
                continue

            if stripped.startswith("%"):
                continue

            cleaned = re.sub(r"(?<!\\)%.*$", "", line)
            if cleaned.strip() or not line.strip():
                result.append(cleaned.rstrip())

        return "\n".join(result)

    def _split_preamble_body(self, content: str) -> tuple:
        """分离 preamble 和 body"""
        match = re.search(r"\\begin\{document\}", content)
        if match:
            end_idx = match.end()
            preamble = content[:end_idx]
            body = content[end_idx:]
            return preamble, body
        return "", content

    def _protect_author_block(self, text: str) -> str:
        """保护 \\author{...} 块"""
        pattern = re.compile(r"(\\author\s*\{)", re.DOTALL)
        result = []
        pos = 0

        for match in pattern.finditer(text):
            result.append(text[pos : match.start()])
            start = match.end()
            brace_count = 1
            i = start

            while i < len(text) and brace_count > 0:
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                i += 1

            if brace_count == 0:
                full_block = match.group(0) + text[start:i]
                self.protected_counter += 1
                placeholder = f"[[AUTHOR_{self.protected_counter}]]"
                chunk_id = str(uuid.uuid4())
                chunk = Chunk(
                    id=chunk_id,
                    content=placeholder,
                    latex_wrapper="%s",
                    context="protected",
                    preserved_elements={placeholder: full_block},
                )
                self.chunks.append(chunk)
                result.append(placeholder)
                pos = i
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)

    def _extract_captions(self, text: str) -> str:
        """提取 caption 内容"""
        pattern = re.compile(r"(\\caption)(\*?)(\s*\[[^\]]*\])?\s*\{")
        result = []
        pos = 0

        for match in pattern.finditer(text):
            result.append(text[pos : match.start()])
            start = match.end()
            brace_count = 1
            i = start

            while i < len(text) and brace_count > 0:
                if text[i] == "{":
                    brace_count += 1
                elif text[i] == "}":
                    brace_count -= 1
                i += 1

            if brace_count == 0:
                content = text[start : i - 1]
                if (
                    content.strip()
                    and not content.startswith("[[")
                    and not content.startswith("{{CHUNK_")
                    and len(content.strip()) > 10
                ):
                    chunk_id = str(uuid.uuid4())
                    placeholder = f"{{{{CHUNK_{chunk_id}}}}}"
                    chunk = Chunk(
                        id=chunk_id,
                        content=content.strip(),
                        latex_wrapper="%s",
                        context="caption",
                        preserved_elements={},
                    )
                    self.chunks.append(chunk)
                    optional_short = match.group(3) if match.group(3) else ""
                    caption_str = (
                        match.group(1)
                        + match.group(2)
                        + optional_short
                        + "{"
                        + placeholder
                        + "}"
                    )
                    result.append(caption_str)
                else:
                    result.append(match.group(0) + content + "}")
                pos = i
            else:
                result.append(match.group(0))
                pos = match.end()

        result.append(text[pos:])
        return "".join(result)


def main():
    print(f"=== Debug Step 1: Parse 初始阶段 ===")
    print(f"Source: {SOURCE_FILE}")
    print()

    if not SOURCE_FILE.exists():
        print(f"ERROR: Source file not found: {SOURCE_FILE}")
        return

    with open(SOURCE_FILE, "r", encoding="utf-8") as f:
        content = f.read()

    print(f"原始文件: {len(content)} 字符, {len(content.splitlines())} 行")

    parser = DebugParser()
    base_dir = str(SOURCE_FILE.parent)

    # Step 1: Flatten
    print("\n--- Step 1.1: Flatten LaTeX ---")
    flattened = parser._flatten_latex(content, base_dir)
    print(f"展开后: {len(flattened)} 字符, {len(flattened.splitlines())} 行")

    # 保存中间产物
    (DEBUG_DIR / "01_flattened.tex").write_text(flattened, encoding="utf-8")
    print(f"保存: debug/01_flattened.tex")

    # Step 2: Remove comments
    print("\n--- Step 1.2: Remove Comments ---")
    no_comments = parser._remove_comments(flattened)
    print(f"去注释后: {len(no_comments)} 字符, {len(no_comments.splitlines())} 行")

    (DEBUG_DIR / "02_no_comments.tex").write_text(no_comments, encoding="utf-8")
    print(f"保存: debug/02_no_comments.tex")

    # Step 3: Split preamble/body
    print("\n--- Step 1.3: Split Preamble/Body ---")
    preamble, body = parser._split_preamble_body(no_comments)
    print(f"Preamble: {len(preamble)} 字符, {len(preamble.splitlines())} 行")
    print(f"Body: {len(body)} 字符, {len(body.splitlines())} 行")

    (DEBUG_DIR / "03_preamble.tex").write_text(preamble, encoding="utf-8")
    (DEBUG_DIR / "03_body.tex").write_text(body, encoding="utf-8")
    print(f"保存: debug/03_preamble.tex, debug/03_body.tex")

    # Step 4: Protect author block
    print("\n--- Step 1.4: Protect Author Block ---")
    body_protected_author = parser._protect_author_block(body)
    print(
        f"Author chunks created: {len([c for c in parser.chunks if c.context == 'protected'])}"
    )

    (DEBUG_DIR / "04_body_author_protected.tex").write_text(
        body_protected_author, encoding="utf-8"
    )
    print(f"保存: debug/04_body_author_protected.tex")

    # Step 5: Extract captions
    print("\n--- Step 1.5: Extract Captions ---")
    body_captions = parser._extract_captions(body_protected_author)
    caption_chunks = [c for c in parser.chunks if c.context == "caption"]
    print(f"Caption chunks created: {len(caption_chunks)}")

    (DEBUG_DIR / "05_body_captions_extracted.tex").write_text(
        body_captions, encoding="utf-8"
    )
    print(f"保存: debug/05_body_captions_extracted.tex")

    # 打印 caption chunks 详情
    print("\n=== Caption Chunks 详情 ===")
    for i, chunk in enumerate(caption_chunks):
        content_preview = chunk.content[:100].replace("\n", " ")
        if len(chunk.content) > 100:
            content_preview += "..."
        print(f"{i + 1}. [{chunk.id[:8]}] {content_preview}")

    # 保存 chunks 信息
    chunks_info = []
    for c in parser.chunks:
        chunks_info.append(
            {
                "id": c.id,
                "context": c.context,
                "content_preview": c.content[:200]
                if len(c.content) <= 200
                else c.content[:200] + "...",
                "content_length": len(c.content),
            }
        )

    import json

    (DEBUG_DIR / "05_chunks.json").write_text(
        json.dumps(chunks_info, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\n保存: debug/05_chunks.json")

    print("\n=== Step 1 完成 ===")
    print("请检查以下文件:")
    print("  - debug/01_flattened.tex      # 展开 \\input 后的完整文档")
    print("  - debug/02_no_comments.tex    # 移除注释后")
    print("  - debug/03_preamble.tex       # 导言区")
    print("  - debug/03_body.tex           # 文档主体（原始）")
    print("  - debug/04_body_author_protected.tex  # 保护 author 后")
    print("  - debug/05_body_captions_extracted.tex # 提取 caption 后")
    print("  - debug/05_chunks.json        # 已创建的 chunks")


if __name__ == "__main__":
    main()
