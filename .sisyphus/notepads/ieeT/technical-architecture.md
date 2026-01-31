# ieeT 技术架构文档

## 概述

ieeT 是一个 arXiv 论文翻译 CLI 工具，将英文 LaTeX 论文翻译为中文 PDF。

## 核心架构

```
┌─────────────────────────────────────────────────────────────────┐
│                         ieet CLI                                │
├─────────────────────────────────────────────────────────────────┤
│  1. Download    │  2. Parse     │  3. Translate  │  4. Compile  │
│  ────────────   │  ──────────   │  ────────────  │  ──────────  │
│  ArxivDownloader│  LaTeXParser  │  Pipeline      │  LaTeXCompiler│
│  ↓              │  ↓            │  ↓             │  ↓           │
│  .tar.gz → .tex │  .tex → Chunks│  Chunks → 中文  │  .tex → PDF  │
└─────────────────────────────────────────────────────────────────┘
```

## Chunk 分割逻辑

### 当前实现 (`src/ieet/parser/chunker.py`)

```python
class LatexChunker:
    # 保护的元素类型
    SECTION_MACROS = {'section', 'subsection', 'caption', 'title', 'abstract'}
    INLINE_PROTECTED = {'cite', 'ref', 'eqref', 'label', 'url'}
    
    def chunk_nodes(self, nodes):
        # 遍历 LaTeX AST 节点
        for node in nodes:
            if isinstance(node, LatexCharsNode):
                # 按双换行符分割段落
                if '\n\n' in text:
                    self._flush_chunk()  # 创建新 chunk
            elif isinstance(node, LatexMathNode):
                # 数学公式 → 占位符 [[MATH_n]]
                self._handle_protected_element(node, "MATH")
            elif isinstance(node, LatexMacroNode):
                if name in SECTION_MACROS:
                    # 章节标题 → 独立 chunk
                    self._flush_chunk()
                elif name in INLINE_PROTECTED:
                    # 引用等 → 占位符 [[REF_n]]
                    self._handle_protected_element(node, "REF")
```

### 分块示例

**原文**:
```latex
This is paragraph 1. The equation $E=mc^2$ is famous.

This is paragraph 2 with \cite{einstein}.
```

**分块结果**:
```
Chunk 1: 
  content: "This is paragraph 1. The equation [[MATH_0]] is famous."
  preserved: {"[[MATH_0]]": "$E=mc^2$"}

Chunk 2:
  content: "This is paragraph 2 with [[REF_0]]."
  preserved: {"[[REF_0]]": "\\cite{einstein}"}
```

## 并发翻译实现

### 参考脚本 (用户验证通过)

```python
async def run_concurrent_requests_async(num_requests=20, semaphore_limit=20):
    semaphore = asyncio.Semaphore(semaphore_limit)
    
    async def limited_send(msg_id, content):
        async with semaphore:
            return await send_message_async(msg_id, content)
    
    tasks = [limited_send(i, messages[i]) for i in range(num_requests)]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

### 当前 Pipeline 实现 (`src/ieet/translator/pipeline.py`)

```python
async def translate_document(self, chunks, context, max_concurrent=20):
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def translate_with_semaphore(chunk_data):
        async with semaphore:
            return await self.translate_chunk(
                chunk=chunk_data["content"],
                chunk_id=chunk_data["chunk_id"],
                context=context,
            )
    
    tasks = [translate_with_semaphore(c) for c in pending_chunks]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results
```

## 翻译提示词

```python
SYSTEM_PROMPT = """你是专业的学术论文翻译专家。你的任务是将英文学术文本改写为流畅自然的中文。

## 核心规则
1. 这是"改写"任务，不是逐词翻译
2. 保持学术严谨性和专业术语准确性
3. 绝对不要修改以下内容（必须原样保留）：
   - LaTeX 命令：\cite{...}, \ref{...}, $...$
   - 占位符：[[MATH_0]], [[REF_1]], [[MACRO_2]]
4. 只输出翻译结果，不要添加解释
5. 如果输入只包含占位符，直接原样返回
"""
```

## 配置系统

### 用户配置 (`~/.ieet/config.yaml`)

```yaml
llm:
  provider: openai
  model: claude-sonnet-4-5
  api_key: sk-xxx
  base_url: http://127.0.0.1:8045/v1
  temperature: 0.1

compilation:
  engine: xelatex
  timeout: 300
```

### 词表 (`~/.ieet/glossary.yaml`)

```yaml
"LLM": "LLM"
"Transformer": "Transformer"
"Attention": "注意力机制"
```

---

## 待改进项

### 1. Chunk 粗粒化 (高优先级)

**问题**: 当前按段落分割过细，每个段落独立翻译，LLM 缺乏上下文

**改进方案**:
```python
def chunk_nodes(self, nodes, target_tokens=800, max_tokens=1500):
    current_chunk = []
    current_tokens = 0
    
    for node in nodes:
        node_tokens = estimate_tokens(node)
        if current_tokens + node_tokens > max_tokens:
            yield merge_nodes(current_chunk)
            current_chunk = [node]
            current_tokens = node_tokens
        else:
            current_chunk.append(node)
            current_tokens += node_tokens
```

### 2. 并发进度条 (高优先级)

**问题**: 并发翻译时无进度显示

**改进方案**:
```python
async def translate_document_with_progress(self, chunks, console):
    from rich.progress import Progress
    
    completed = 0
    lock = asyncio.Lock()
    
    with Progress(console=console) as progress:
        task = progress.add_task("Translating...", total=len(chunks))
        
        async def translate_and_update(chunk):
            nonlocal completed
            result = await self.translate_chunk(chunk)
            async with lock:
                completed += 1
                progress.update(task, completed=completed)
            return result
        
        tasks = [translate_and_update(c) for c in chunks]
        return await asyncio.gather(*tasks)
```

### 3. 上下文传递 (中优先级)

**改进方案**: 翻译时传递前后 chunk 摘要

```python
async def translate_with_context(self, chunks):
    results = []
    for i, chunk in enumerate(chunks):
        prev_summary = summarize(chunks[i-1]) if i > 0 else None
        next_summary = summarize(chunks[i+1]) if i < len(chunks)-1 else None
        
        context = f"前文: {prev_summary}\n后文: {next_summary}"
        result = await self.translate_chunk(chunk, context=context)
        results.append(result)
    return results
```

## Git 提交记录

```
commit bfe1b46 - feat: implement concurrent translation (max 20 parallel requests)
commit 5dab86f - feat: initial project setup with docs and config
```
