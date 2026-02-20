# 修复 \paragraph 同行正文未翻译问题

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 修复 `_extract_section_command()` 方法，使同行正文（`\paragraph{\textbf{Title}} Body text`）被正确识别为可翻译内容

**架构思路:** 在提取 section command 的 title 内容后，检查同一行是否还有剩余正文。如果有，则在替换后的结构后插入换行符，使 `_chunk_paragraphs()` 将其识别为独立段落而非结构行的一部分。

**技术栈:** Python 3.10+, pytest

---

## Task 1: 创建回归测试

**Files:**
- Create: `tests/test_paragraph_inline_body.py`

**Step 1: 编写测试文件**

```python
"""Tests for paragraph inline body text extraction."""

from ieeA.parser.latex_parser import LaTeXParser


def _extract_paragraph_chunks(text: str):
    """Helper to extract paragraph-related chunks from text."""
    parser = LaTeXParser()
    parser.chunks = []
    parser.protected_counter = 0
    parser.placeholder_map = {}
    processed = parser._extract_section_command(text, "paragraph")
    # Run chunk paragraphs to see the actual chunks that would be created
    final = parser._chunk_paragraphs(processed)
    paragraphs = [c for c in parser.chunks if c.context == "paragraph"]
    return parser, processed, final, paragraphs


def test_paragraph_with_inline_body_is_translatable():
    """\paragraph{Title} Body text should have body as separate translatable chunk."""
    text = r"\paragraph{\textbf{Title}} Body text that should be translatable."
    parser, processed, final, paragraphs = _extract_paragraph_chunks(text)

    # The title should be extracted as a chunk
    chunk_titles = [c.content for c in parser.chunks if "Title" in c.content]
    assert any("Title" in t for t in chunk_titles), "Title should be extracted as chunk"

    # The body text should be in a paragraph chunk
    body_paragraphs = [c.content for c in paragraphs]
    assert any("Body text that should be translatable" in p for p in body_paragraphs), \
        f"Body text should be in paragraph chunks. Found: {body_paragraphs}"


def test_paragraph_with_newline_body_still_works():
    """\paragraph{Title}\nBody text should still work (regression test)."""
    text = r"\paragraph{\textbf{Title}}
Body text on new line."
    parser, processed, final, paragraphs = _extract_paragraph_chunks(text)

    # Both title and body should be chunks
    chunk_contents = [c.content for c in parser.chunks]
    assert any("Title" in c for c in chunk_contents), "Title should be chunked"
    assert any("Body text on new line" in c for c in chunk_contents), \
        "Body on new line should be chunked"


def test_paragraph_without_trailing_body_no_extra_newline():
    """\paragraph{Title} alone should not have extra newline issues."""
    text = r"\paragraph{\textbf{Title}}"
    parser, processed, final, paragraphs = _extract_paragraph_chunks(text)

    # Should have exactly one chunk (the title)
    assert len(parser.chunks) == 1, f"Expected 1 chunk, got {len(parser.chunks)}: {[c.content for c in parser.chunks]}"
    assert parser.chunks[0].content == r"\textbf{Title}"


def test_multiple_paragraphs_with_inline_bodies():
    """Multiple \paragraph commands with inline bodies should all be handled."""
    text = r"""\paragraph{First} First body text.
\paragraph{Second} Second body text.
Normal paragraph."""
    parser, processed, final, paragraphs = _extract_paragraph_chunks(text)

    chunk_contents = [c.content for c in parser.chunks]
    assert any("First" in c for c in chunk_contents), "First title should be chunked"
    assert any("Second" in c for c in chunk_contents), "Second title should be chunked"
    assert any("First body text" in c for c in chunk_contents), "First body should be chunked"
    assert any("Second body text" in c for c in chunk_contents), "Second body should be chunked"
```

**Step 2: 运行测试确认失败**

```bash
python -m pytest tests/test_paragraph_inline_body.py -v
```

Expected: 4 tests, at least `test_paragraph_with_inline_body_is_translatable` and `test_multiple_paragraphs_with_inline_bodies` should FAIL

**Step 3: 提交测试文件**

```bash
git add tests/test_paragraph_inline_body.py
git commit -m "test: 添加 \paragraph 同行正文未翻译问题的回归测试"
```

---

## Task 2: 实现修复

**Files:**
- Modify: `src/ieeA/parser/latex_parser.py:754-757`

**Step 1: 修改代码**

修改 `_extract_section_command()` 方法，在 Line 754 的 `pos = i` 后添加换行符检查逻辑：

```python
                pos = i
                # If trailing body text exists on same line after section
                # command's closing brace, insert newline so _chunk_paragraphs
                # treats it as a separate translatable paragraph instead of
                # part of the structural line.
                next_nl = text.find('\n', i)
                trailing_on_line = text[i:next_nl] if next_nl >= 0 else text[i:]
                if trailing_on_line.strip():
                    result.append('\n')
            else:
                result.append(match.group(0))
                pos = match.end()
```

**插入位置确认:**
- Line 754: 在 `if brace_count == 0:` 分支内的 `pos = i` 之后（第一个插入点）
- 同样逻辑需要在处理 empty/placeholder 内容的 `if brace_count == 0:` 分支（line 732-736）中添加

**Step 2: 验证两个分支都被覆盖**

确认修改覆盖了以下两个位置：
1. Line 732-736 分支（empty/placeholder content）
2. Line 747-754 分支（normal extracted content）

两个分支都应该在 `pos = i` 后添加换行符检查逻辑。

**Step 3: 运行测试验证修复**

```bash
python -m pytest tests/test_paragraph_inline_body.py -v
```

Expected: 4 tests all PASS

---

## Task 3: 运行全量回归测试

**Step 1: 运行所有 parser 相关测试**

```bash
python -m pytest tests/test_parser_chunk_consistency.py tests/2026-02-07/ -v
```

Expected: All PASS

**Step 2: 运行全量测试套件**

```bash
python -m pytest tests/ -x -v
```

Expected: All PASS

---

## Task 4: Git 提交

**Step 1: 检查改动**

```bash
git diff src/ieeA/parser/latex_parser.py
```

**Step 2: 提交修复**

```bash
git add src/ieeA/parser/latex_parser.py
git commit -m "修复: \paragraph 同行正文未被识别为可翻译内容的问题"
```

---

## Task 5: 手动验证（可选但建议）

**Step 1: 准备测试文档**

创建一个包含以下内容的测试文件 `/tmp/test_para.tex`：

```latex
\documentclass{article}
\begin{document}
\paragraph{\textbf{Test Title}} This body text should be translated.
\end{document}
```

**Step 2: 使用 parser 解析并检查输出**

```python
from ieeA.parser.latex_parser import LaTeXParser
import tempfile

with tempfile.NamedTemporaryFile(mode='w', suffix='.tex', delete=False) as f:
    f.write(r"""\documentclass{article}
\begin{document}
\paragraph{\textbf{Test Title}} This body text should be translated.
\end{document}""")
    path = f.name

parser = LaTeXParser()
doc = parser.parse_file(path)
print("Chunks:")
for c in doc.chunks:
    print(f"  [{c.context}] {c.content[:80]}...")
print("\nBody template preview:")
print(doc.body_template[:500])
```

Expected Output:
- 至少 2 个 chunks: 一个是 title (\textbf{Test Title})，一个是 body ("This body text should be translated.")
- Body template 中 body text 应该被替换为 {{CHUNK_xxxx}} 占位符

---

## 验收标准

1. **测试通过**: `tests/test_paragraph_inline_body.py` 4 个测试全部通过
2. **回归通过**: `python -m pytest tests/ -x -v` 全量测试通过
3. **代码提交**: Git commit 包含 "修复: \paragraph 同行正文未被识别为可翻译内容的问题"
4. **代码质量**: 改动仅限于 `_extract_section_command` 方法，新增逻辑有完整注释

## 注意事项

1. **分支覆盖**: 确保两个 `if brace_count == 0:` 分支都添加了换行符检查
2. **测试独立**: 新测试文件不依赖其他测试的顺序
3. **无副作用**: 确认修改不会影响到没有同行正文的 \paragraph 命令