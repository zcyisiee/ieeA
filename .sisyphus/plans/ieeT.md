# ieeT - arXiv 论文翻译工具

## TL;DR

> **Quick Summary**: 构建一个 CLI 工具，输入 arXiv 链接，下载 LaTeX 源码，使用 LLM 进行 chunk 级别翻译，输出中文 PDF。核心特点是可扩展的规则系统，让用户能自定义修复规则。
> 
> **Deliverables**:
> - `ieeet` CLI 工具 (Python)
> - LaTeX 解析器 (pylatexenc + 自定义逻辑)
> - 多模型 LLM 翻译层
> - YAML 规则系统 (词表 + 验证规则)
> - PDF 编译输出
> 
> **Estimated Effort**: Large (2-3 周)
> **Parallel Execution**: YES - 3 waves
> **Critical Path**: Phase 0 验证 → 解析器 → 翻译器 → 编译器

---

## Context

### Original Request
开发一款翻译软件，输入是 arXiv 链接，输出是中英文对照 PDF。参考 hjfy.top (幻觉翻译)，重点是：
1. 按最小节 chunk 翻译
2. 意译/改写风格
3. 高可扩展性：用户词表 + 自定义验证规则

### Interview Summary

**Key Discussions**:
- 技术栈: Python (FastAPI) 后端
- LLM: 多模型支持，抽象层设计
- 部署: 先 CLI，后期加 Web
- 测试: 混合策略 (核心模块 TDD + 集成测试)
- 项目名: ieeT

**Research Findings**:
- hjfy.top 作者教训: PDF→Markdown/Word 都不可行，必须用 LaTeX 源码
- LaTeX 解析: pylatexenc (文本提取) + TexSoup (结构修改)
- arXiv API: python `arxiv` 包，源码从 `/e-print/{id}` 下载

### Metis Review

**Identified Gaps** (addressed):
1. 多文件 LaTeX 处理 → 递归解析 `\input{}` 和 `\include{}`
2. LLM 选择未明确 → 设计抽象层，MVP 支持 OpenAI/Claude/国产模型
3. 中文字体问题 → 使用 Noto CJK 字体，检测并提示安装
4. chunk 粒度未定 → 采用段落级别 (paragraph-level)
5. 缺少验证脚本 → 添加 Phase 0 假设验证

**Additional Guardrails**:
- MVP 仅支持 CLI，不做 Web UI
- 单次单篇论文，不做批处理
- 仅支持 English → Chinese
- 仅支持有源码的论文，不做 PDF OCR

---

## Work Objectives

### Core Objective
构建一个可扩展的 arXiv 论文翻译 CLI 工具，能够将英文 LaTeX 论文翻译为高质量中文 PDF，同时提供清晰的错误诊断和用户自定义规则能力。

### Concrete Deliverables
1. `ieeet` Python CLI 工具 (可通过 pip 安装)
2. LaTeX 解析模块 (`ieeet/parser/`)
3. LLM 翻译模块 (`ieeet/translator/`)
4. 规则引擎 (`ieeet/rules/`)
5. PDF 编译模块 (`ieeet/compiler/`)
6. 默认词表和规则配置 (`ieeet/defaults/`)
7. 用户配置目录 (`~/.ieeet/`)

### Definition of Done
- [ ] `ieeet translate https://arxiv.org/abs/2301.07041` 成功输出中文 PDF
- [ ] 10 篇测试论文中 ≥7 篇编译成功
- [ ] 用户可通过 YAML 添加自定义词表和规则
- [ ] 失败时提供可操作的错误诊断信息

### Must Have
- arXiv 源码下载和解析
- 段落级别 chunk 翻译
- LaTeX 结构完整保留 (数学公式、引用、标签)
- 基础验证规则 (命令保持、括号匹配)
- YAML 词表系统
- YAML 规则系统
- PDF 编译输出

### Must NOT Have (Guardrails)
- ❌ Web UI (MVP 仅 CLI)
- ❌ 批量处理 (单次单篇)
- ❌ PDF OCR 翻译 (仅 LaTeX 源码)
- ❌ 翻译记忆/缓存
- ❌ 用户账户/数据库
- ❌ 多语言支持 (仅 EN→ZH)
- ❌ 翻译质量评分系统

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (新项目)
- **User wants tests**: YES (混合策略)
- **Framework**: pytest

### Test Strategy: 混合模式

**核心模块 (TDD)**:
- LaTeX 解析器
- 规则引擎
- 验证逻辑

**集成测试**:
- 端到端翻译流程
- 使用真实 arXiv 论文

### Test Setup Task
```bash
# 安装测试框架
pip install pytest pytest-asyncio pytest-cov

# 运行测试
pytest tests/ -v --cov=ieeet
```

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 0 (Start Immediately - 假设验证):
└── Task 0: 假设验证脚本

Wave 1 (After Wave 0 - 核心模块并行):
├── Task 1: 项目结构初始化
├── Task 2: arXiv 下载模块
├── Task 3: 配置和规则系统
└── Task 4: LLM 抽象层

Wave 2 (After Wave 1):
├── Task 5: LaTeX 解析器
├── Task 6: 翻译流水线
└── Task 7: 验证引擎

Wave 3 (After Wave 2):
├── Task 8: PDF 编译器
├── Task 9: CLI 接口
└── Task 10: 集成测试和文档

Critical Path: Task 0 → Task 5 → Task 6 → Task 8 → Task 9
```

### Dependency Matrix

| Task | Depends On | Blocks | Can Parallelize With |
|------|------------|--------|---------------------|
| 0 | None | 1-10 | None |
| 1 | 0 | 2,3,4,5,6,7,8,9 | None |
| 2 | 1 | 5,6 | 3, 4 |
| 3 | 1 | 5,6,7 | 2, 4 |
| 4 | 1 | 6 | 2, 3 |
| 5 | 2,3 | 6 | None |
| 6 | 4,5 | 8 | 7 |
| 7 | 3,5 | 8 | 6 |
| 8 | 6,7 | 9 | None |
| 9 | 8 | 10 | None |
| 10 | 9 | None | None |

---

## TODOs

### Phase 0: 假设验证

- [x] 0. 假设验证脚本

  **What to do**:
  - 创建 `scripts/validate_assumptions.py`
  - 下载 10 篇不同类别的 arXiv 论文源码
  - 测试: 源码可用性、文件结构、pylatexenc 解析成功率、主文件检测
  - 输出验证报告

  **Must NOT do**:
  - 不要实现完整的解析逻辑
  - 不要处理所有边缘情况

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 简单的验证脚本，探索性任务

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 0 (独立)
  - **Blocks**: Tasks 1-10
  - **Blocked By**: None

  **References**:
  - arXiv API: `https://arxiv.org/e-print/{id}`
  - pylatexenc 文档: `https://pylatexenc.readthedocs.io/`
  - 测试论文 IDs: `2301.07041`, `1706.03762`, `2305.10601`, `1810.04805`, `2203.02155`

  **Acceptance Criteria**:
  ```bash
  # 运行验证脚本
  python scripts/validate_assumptions.py
  
  # Assert: 输出 validation_report.json
  # Assert: ≥8/10 论文源码可下载
  # Assert: ≥6/10 论文 pylatexenc 可解析
  # Assert: ≥8/10 论文主文件可识别
  ```

  **Commit**: YES
  - Message: `chore: add assumption validation script`
  - Files: `scripts/validate_assumptions.py`, `validation_report.json`

---

### Phase 1: 项目初始化

- [x] 1. 项目结构初始化

  **What to do**:
  - 创建 Python 包结构 (`ieeet/`)
  - 设置 `pyproject.toml` (使用 hatch 或 setuptools)
  - 配置 pytest、ruff、mypy
  - 创建基础目录结构

  **目录结构**:
  ```
  ieeet/
  ├── pyproject.toml
  ├── README.md
  ├── src/
  │   └── ieeet/
  │       ├── __init__.py
  │       ├── cli.py
  │       ├── downloader/
  │       ├── parser/
  │       ├── translator/
  │       ├── validator/
  │       ├── compiler/
  │       ├── rules/
  │       └── defaults/
  ├── tests/
  │   └── __init__.py
  └── scripts/
  ```

  **Must NOT do**:
  - 不要实现具体功能
  - 不要添加过多依赖

  **Recommended Agent Profile**:
  - **Category**: `quick`
  - **Skills**: []
  - Reason: 标准 Python 项目初始化

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 1 (第一个)
  - **Blocks**: Tasks 2,3,4,5,6,7,8,9
  - **Blocked By**: Task 0

  **References**:
  - Python Packaging Guide: `https://packaging.python.org/`
  - pyproject.toml 示例: hatch 或 setuptools 文档

  **Acceptance Criteria**:
  ```bash
  # 安装项目
  pip install -e .
  
  # Assert: 可以导入
  python -c "import ieeet; print(ieeet.__version__)"
  # Assert: 输出版本号 (如 0.1.0)
  
  # Assert: 测试框架工作
  pytest tests/ -v
  # Assert: Exit code 0 (即使没有测试)
  ```

  **Commit**: YES
  - Message: `feat: initialize project structure`
  - Files: `pyproject.toml`, `src/ieeet/__init__.py`, `tests/__init__.py`

---

- [x] 2. arXiv 下载模块

  **What to do**:
  - 实现 `ieeet/downloader/arxiv.py`
  - 功能: 解析 arXiv URL/ID，下载源码 tar.gz，解压，识别主 tex 文件
  - 处理多文件提交 (`\input{}`, `\include{}`)
  - 遵循 arXiv 速率限制 (3秒延迟)

  **Must NOT do**:
  - 不要实现缓存
  - 不要处理 PDF-only 论文

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []
  - Reason: 标准 HTTP 下载和文件处理

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (与 Task 3, 4 并行)
  - **Blocks**: Task 5, 6
  - **Blocked By**: Task 1

  **References**:
  - arxiv Python 包: `pip install arxiv`
  - arXiv API 文档: `https://info.arxiv.org/help/api/index.html`
  - 源码 URL 格式: `https://arxiv.org/e-print/{id}`

  **Acceptance Criteria**:
  ```bash
  # 测试下载功能
  python -c "
  from ieeet.downloader import ArxivDownloader
  d = ArxivDownloader()
  result = d.download('2301.07041', output_dir='./test_dl')
  print(f'Main tex: {result.main_tex}')
  print(f'All files: {result.all_files}')
  "
  
  # Assert: ./test_dl/ 目录存在
  # Assert: 至少有一个 .tex 文件
  # Assert: result.main_tex 不为 None
  ```

  **Commit**: YES
  - Message: `feat(downloader): implement arXiv source download`
  - Files: `src/ieeet/downloader/__init__.py`, `src/ieeet/downloader/arxiv.py`
  - Pre-commit: `pytest tests/test_downloader.py -v`

---

- [x] 3. 配置和规则系统

  **What to do**:
  - 实现 `ieeet/rules/config.py` - 配置加载
  - 实现 `ieeet/rules/glossary.py` - 词表系统
  - 实现 `ieeet/rules/validation_rules.py` - 验证规则定义
  - 使用 Pydantic 进行 YAML 验证
  - 创建默认配置 `ieeet/defaults/`

  **配置结构**:
  ```yaml
  # ~/.ieeet/config.yaml
  llm:
    provider: openai  # openai, claude, qwen, doubao
    model: gpt-4o-mini
    api_key_env: OPENAI_API_KEY
  
  compilation:
    engine: xelatex
    timeout: 120
    
  # ~/.ieeet/glossary.yaml
  glossary:
    attention mechanism: 注意力机制
    transformer: Transformer
    
  # ~/.ieeet/rules.yaml
  rules:
    - id: fix_textbf_space
      pattern: '\\textbf\s*{(.+?)}'
      replacement: '\\textbf{$1}'
      trigger: compilation_error
  ```

  **Must NOT do**:
  - 不要实现规则执行逻辑 (Task 7)
  - 不要硬编码配置值

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []
  - Reason: 配置管理，Pydantic 模型定义

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (与 Task 2, 4 并行)
  - **Blocks**: Task 5, 6, 7
  - **Blocked By**: Task 1

  **References**:
  - Pydantic v2 文档: `https://docs.pydantic.dev/`
  - YAML 加载: `pip install pyyaml`

  **Acceptance Criteria**:
  ```bash
  # 测试配置加载
  python -c "
  from ieeet.rules import Config, Glossary, load_config
  
  # 加载默认配置
  config = load_config()
  print(f'LLM provider: {config.llm.provider}')
  
  # 加载词表
  glossary = Glossary.load_default()
  print(f'Glossary entries: {len(glossary.entries)}')
  "
  
  # Assert: 配置加载成功
  # Assert: 默认词表有 >10 个条目
  ```

  **Commit**: YES
  - Message: `feat(rules): implement config and glossary system`
  - Files: `src/ieeet/rules/*.py`, `src/ieeet/defaults/*.yaml`
  - Pre-commit: `pytest tests/test_rules.py -v`

---

- [x] 4. LLM 抽象层

  **What to do**:
  - 实现 `ieeet/translator/llm_base.py` - 抽象基类
  - 实现 `ieeet/translator/openai_provider.py` - OpenAI 适配器
  - 实现 `ieeet/translator/claude_provider.py` - Claude 适配器
  - 实现 `ieeet/translator/qwen_provider.py` - 通义千问适配器
  - 统一的翻译接口: `translate(text, context, glossary_hints) -> str`

  **接口设计**:
  ```python
  class LLMProvider(ABC):
      @abstractmethod
      async def translate(
          self,
          text: str,
          context: str,
          glossary_hints: list[str],
          few_shot_examples: list[tuple[str, str]]
      ) -> str:
          pass
      
      @abstractmethod
      def estimate_tokens(self, text: str) -> int:
          pass
  ```

  **Must NOT do**:
  - 不要实现翻译流水线逻辑 (Task 6)
  - 不要实现重试逻辑 (在 Task 6 中处理)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []
  - Reason: API 封装，异步编程

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (与 Task 2, 3 并行)
  - **Blocks**: Task 6
  - **Blocked By**: Task 1

  **References**:
  - OpenAI Python SDK: `pip install openai`
  - Anthropic SDK: `pip install anthropic`
  - 通义千问 SDK: `pip install dashscope`

  **Acceptance Criteria**:
  ```bash
  # 测试 LLM 提供者 (需要 API key)
  python -c "
  from ieeet.translator import get_provider
  
  provider = get_provider('openai', model='gpt-4o-mini')
  # 仅测试初始化，不实际调用 API
  print(f'Provider: {provider.__class__.__name__}')
  print(f'Token estimate: {provider.estimate_tokens(\"Hello world\")}')
  "
  
  # Assert: 提供者初始化成功
  # Assert: token 估算返回 >0 的整数
  ```

  **Commit**: YES
  - Message: `feat(translator): implement LLM provider abstraction`
  - Files: `src/ieeet/translator/*.py`
  - Pre-commit: `pytest tests/test_translator.py -v`

---

### Phase 2: 核心模块

- [x] 5. LaTeX 解析器

  **What to do**:
  - 实现 `ieeet/parser/latex_parser.py` - 主解析器
  - 实现 `ieeet/parser/chunker.py` - chunk 提取器
  - 实现 `ieeet/parser/structure.py` - 文档结构表示
  - 功能:
    - 提取 preamble (永不翻译)
    - 识别可翻译区域 (段落、标题、caption)
    - 保护不可翻译区域 (数学、代码、引用)
    - 递归解析 `\input{}` 和 `\include{}`
    - 输出 chunk 列表，每个 chunk 包含原文和上下文

  **Chunk 数据结构**:
  ```python
  @dataclass
  class Chunk:
      id: str
      content: str           # 待翻译文本
      latex_wrapper: str     # 包裹的 LaTeX 结构
      context: str           # 上下文提示
      preserved: list[str]   # 保护的内联元素 (如 $...$)
      source_location: SourceLocation
  ```

  **Must NOT do**:
  - 不要实现翻译逻辑
  - 不要处理所有 LaTeX 宏 (只处理常见的)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 复杂的解析逻辑，需要深入理解 LaTeX

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 2 (依赖 Wave 1)
  - **Blocks**: Task 6
  - **Blocked By**: Task 2, 3

  **References**:
  - pylatexenc: `pip install pylatexenc`
  - TexSoup: `pip install TexSoup`
  - hjfy.top 作者博客: 解析策略参考

  **Acceptance Criteria**:
  ```bash
  # 测试解析器
  python -c "
  from ieeet.parser import LaTeXParser
  
  parser = LaTeXParser()
  
  # 测试简单文档
  doc = r'''
  \documentclass{article}
  \begin{document}
  \section{Introduction}
  This is a test. The equation \$E=mc^2\$ is famous.
  \end{document}
  '''
  
  result = parser.parse(doc)
  chunks = result.get_translatable_chunks()
  
  print(f'Preamble preserved: {\"documentclass\" in result.preamble}')
  print(f'Chunks found: {len(chunks)}')
  print(f'Math preserved: {\"\$E=mc^2\$\" in str(chunks)}')
  "
  
  # Assert: preamble 被保留
  # Assert: 至少找到 1 个 chunk
  # Assert: 数学公式被保护
  
  # 使用真实论文测试
  python -c "
  from ieeet.downloader import ArxivDownloader
  from ieeet.parser import LaTeXParser
  
  d = ArxivDownloader()
  result = d.download('2301.07041', './test_parse')
  
  parser = LaTeXParser()
  doc = parser.parse_file(result.main_tex)
  chunks = doc.get_translatable_chunks()
  
  print(f'Real paper chunks: {len(chunks)}')
  "
  
  # Assert: 真实论文能解析出 >10 个 chunks
  ```

  **Commit**: YES
  - Message: `feat(parser): implement LaTeX parser and chunker`
  - Files: `src/ieeet/parser/*.py`, `tests/test_parser.py`
  - Pre-commit: `pytest tests/test_parser.py -v`

---

- [x] 6. 翻译流水线

  **What to do**:
  - 实现 `ieeet/translator/pipeline.py` - 翻译流水线
  - 功能:
    - 接收 chunk 列表
    - 应用词表预处理 (术语占位符)
    - 构建翻译 prompt (few-shot + 词表提示 + 上下文)
    - 调用 LLM 翻译
    - 词表后处理 (恢复占位符)
    - 返回翻译后的 chunk 列表
  - 实现速率限制和重试逻辑
  - 支持断点续传 (保存中间状态)

  **翻译 Prompt 模板**:
  ```
  你是一位专业的学术论文翻译专家。请将以下英文学术文本翻译成中文。

  翻译要求：
  1. 采用意译/改写风格，保证中文表达自然流畅
  2. 保持所有 LaTeX 命令不变（如 \cite{}, \ref{}, $...$）
  3. 专业术语遵循以下对照表：
  {glossary_hints}

  上下文信息：
  {context}

  待翻译文本：
  {content}

  翻译结果：
  ```

  **Must NOT do**:
  - 不要实现验证逻辑 (Task 7)
  - 不要实现编译逻辑 (Task 8)

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 复杂的异步流水线，需要处理多种边缘情况

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (与 Task 7 并行)
  - **Blocks**: Task 8
  - **Blocked By**: Task 4, 5

  **References**:
  - asyncio 文档
  - LLM 提示工程最佳实践

  **Acceptance Criteria**:
  ```bash
  # 测试翻译流水线 (需要 API key)
  python -c "
  from ieeet.translator import TranslationPipeline
  from ieeet.parser import Chunk
  from ieeet.rules import load_config, Glossary
  
  config = load_config()
  glossary = Glossary.load_default()
  
  pipeline = TranslationPipeline(config, glossary)
  
  # 测试单个 chunk
  chunk = Chunk(
      id='test_1',
      content='Attention mechanisms have become an integral part of neural networks.',
      latex_wrapper='',
      context='Introduction section',
      preserved=[],
      source_location=None
  )
  
  import asyncio
  result = asyncio.run(pipeline.translate_chunk(chunk))
  
  print(f'Translated: {result.translated[:50]}...')
  print(f'Contains Chinese: {any(\"\\u4e00\" <= c <= \"\\u9fff\" for c in result.translated)}')
  "
  
  # Assert: 翻译结果包含中文字符
  # Assert: 没有 LaTeX 命令被破坏
  ```

  **Commit**: YES
  - Message: `feat(translator): implement translation pipeline`
  - Files: `src/ieeet/translator/pipeline.py`, `tests/test_pipeline.py`
  - Pre-commit: `pytest tests/test_pipeline.py -v`

---

- [x] 7. 验证引擎

  **What to do**:
  - 实现 `ieeet/validator/engine.py` - 验证引擎
  - 实现 `ieeet/validator/rules/` - 内置验证规则
  - 功能:
    - 结构验证: LaTeX 命令保持、括号匹配、引用完整
    - 语义验证: 词表合规、长度比例检查
    - 自动修复: 应用用户定义的修复规则
    - 错误报告: 清晰的错误位置和修复建议

  **验证规则类型**:
  ```python
  class ValidationResult:
      passed: bool
      errors: list[ValidationError]
      warnings: list[ValidationWarning]
      auto_fixes_applied: list[str]
  
  class ValidationError:
      rule_id: str
      message: str
      location: SourceLocation
      suggested_fix: str | None
      can_auto_fix: bool
  ```

  **Must NOT do**:
  - 不要实现 LLM 辅助验证 (后续版本)
  - 不要实现复杂的语义理解

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: 规则引擎设计，需要可扩展架构

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (与 Task 6 并行)
  - **Blocks**: Task 8
  - **Blocked By**: Task 3, 5

  **References**:
  - hjfy.top 作者博客: 后检查机制
  - 正则表达式文档

  **Acceptance Criteria**:
  ```bash
  # 测试验证引擎
  python -c "
  from ieeet.validator import ValidationEngine
  from ieeet.rules import load_rules
  
  engine = ValidationEngine(load_rules())
  
  # 测试正确的翻译
  good = r'这是一个关于 \$E=mc^2\$ 的测试。参见 \cite{einstein1905}。'
  result = engine.validate(good, original='This is a test about \$E=mc^2\$. See \cite{einstein1905}.')
  print(f'Good translation passed: {result.passed}')
  
  # 测试错误的翻译 (引用被修改)
  bad = r'这是一个关于 \$E=mc^2\$ 的测试。参见引用。'
  result = engine.validate(bad, original='This is a test about \$E=mc^2\$. See \cite{einstein1905}.')
  print(f'Bad translation passed: {result.passed}')
  print(f'Errors: {[e.rule_id for e in result.errors]}')
  "
  
  # Assert: 正确翻译通过验证
  # Assert: 错误翻译不通过，且报告 citation_preserved 错误
  ```

  **Commit**: YES
  - Message: `feat(validator): implement validation engine`
  - Files: `src/ieeet/validator/*.py`, `tests/test_validator.py`
  - Pre-commit: `pytest tests/test_validator.py -v`

---

### Phase 3: 输出和集成

- [x] 8. PDF 编译器

  **What to do**:
  - 实现 `ieeet/compiler/latex_compiler.py` - LaTeX 编译器
  - 实现 `ieeet/compiler/chinese_support.py` - 中文支持注入
  - 功能:
    - 注入中文支持包 (xeCJK, ctex)
    - 配置中文字体 (Noto CJK)
    - 调用 xelatex 编译
    - 处理编译错误，提取有用信息
    - 多级回退策略 (xelatex → lualatex → pdflatex)

  **中文支持注入**:
  ```latex
  % 在 \documentclass 后注入
  \usepackage{xeCJK}
  \setCJKmainfont{Noto Serif CJK SC}
  \setCJKsansfont{Noto Sans CJK SC}
  \setCJKmonofont{Noto Sans Mono CJK SC}
  ```

  **Must NOT do**:
  - 不要实现 paracol 双语 PDF (后续版本)
  - 不要实现远程编译服务

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
  - **Skills**: []
  - Reason: LaTeX 编译复杂，需要处理多种错误情况

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 9
  - **Blocked By**: Task 6, 7

  **References**:
  - xelatex 文档
  - xeCJK 包文档
  - Noto CJK 字体: `https://github.com/notofonts/noto-cjk`

  **Acceptance Criteria**:
  ```bash
  # 测试编译器
  python -c "
  from ieeet.compiler import LaTeXCompiler
  
  compiler = LaTeXCompiler()
  
  # 测试简单中文文档
  doc = r'''
  \documentclass{article}
  \begin{document}
  这是一个中文测试文档。
  
  公式测试：\$E=mc^2\$
  \end{document}
  '''
  
  result = compiler.compile(doc, output_path='./test_output.pdf')
  print(f'Compilation success: {result.success}')
  if not result.success:
      print(f'Errors: {result.errors[:200]}')
  "
  
  # Assert: 编译成功
  # Assert: ./test_output.pdf 存在
  # Assert: PDF 页数 > 0 (用 pdfinfo 检查)
  
  # 检查 PDF
  pdfinfo ./test_output.pdf | grep Pages
  # Assert: Pages: 1 (或更多)
  ```

  **Commit**: YES
  - Message: `feat(compiler): implement LaTeX compiler with Chinese support`
  - Files: `src/ieeet/compiler/*.py`, `tests/test_compiler.py`
  - Pre-commit: `pytest tests/test_compiler.py -v`

---

- [x] 9. CLI 接口

  **What to do**:
  - 实现 `ieeet/cli.py` - CLI 入口
  - 使用 `typer` 或 `click` 构建 CLI
  - 命令:
    - `ieeet translate <arxiv_url> [--output <path>]` - 主命令
    - `ieeet config` - 显示/编辑配置
    - `ieeet glossary add <term> <translation>` - 添加词表
    - `ieeet validate <tex_file>` - 验证 LaTeX 文件
  - 进度显示: 使用 `rich` 显示进度条
  - 错误报告: 清晰的错误信息和修复建议

  **CLI 示例**:
  ```bash
  # 翻译论文
  ieeet translate https://arxiv.org/abs/2301.07041 --output ./output.pdf
  
  # 使用自定义配置
  ieeet translate 2301.07041 --llm claude --model claude-3-sonnet
  
  # 添加词表
  ieeet glossary add "attention mechanism" "注意力机制"
  
  # 查看配置
  ieeet config show
  ```

  **Must NOT do**:
  - 不要实现交互式模式
  - 不要实现批量处理

  **Recommended Agent Profile**:
  - **Category**: `unspecified-low`
  - **Skills**: []
  - Reason: CLI 开发相对直接

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3
  - **Blocks**: Task 10
  - **Blocked By**: Task 8

  **References**:
  - Typer 文档: `https://typer.tiangolo.com/`
  - Rich 文档: `https://rich.readthedocs.io/`

  **Acceptance Criteria**:
  ```bash
  # 测试 CLI
  ieeet --help
  # Assert: 显示帮助信息
  
  ieeet translate --help
  # Assert: 显示 translate 命令帮助
  
  # 端到端测试 (需要 API key)
  ieeet translate https://arxiv.org/abs/2301.07041 --output ./e2e_test.pdf
  # Assert: Exit code 0
  # Assert: ./e2e_test.pdf 存在
  
  # 检查 PDF
  pdfinfo ./e2e_test.pdf | grep Pages
  # Assert: Pages > 0
  ```

  **Commit**: YES
  - Message: `feat(cli): implement CLI interface`
  - Files: `src/ieeet/cli.py`, `tests/test_cli.py`
  - Pre-commit: `pytest tests/test_cli.py -v`

---

- [ ] 10. 集成测试和文档

  **What to do**:
  - 创建端到端集成测试
  - 测试 10 篇不同类别的真实 arXiv 论文
  - 编写用户文档:
    - README.md (快速开始)
    - docs/installation.md (安装指南)
    - docs/configuration.md (配置说明)
    - docs/custom-rules.md (自定义规则指南)
    - docs/troubleshooting.md (故障排除)
  - 记录已知限制

  **测试论文列表**:
  | arXiv ID | 类别 | 特点 |
  |----------|------|------|
  | 2301.07041 | CS.CL | 标准 NLP 论文 |
  | 1706.03762 | CS.CL | Transformer 原文 |
  | 2305.10601 | CS.CL | 较新的论文 |
  | 1810.04805 | CS.CL | BERT 论文 |
  | 2203.02155 | CS.CV | 视觉论文 |
  | 1312.6114 | CS.LG | VAE 论文 |
  | 2006.11239 | CS.LG | DDPM 论文 |
  | 1409.1556 | CS.CV | VGGNet |
  | 1512.03385 | CS.CV | ResNet |
  | 2010.11929 | CS.CV | ViT 论文 |

  **Must NOT do**:
  - 不要实现自动化 CI/CD (后续)
  - 不要编写开发者文档 (仅用户文档)

  **Recommended Agent Profile**:
  - **Category**: `writing`
  - **Skills**: []
  - Reason: 文档编写任务

  **Parallelization**:
  - **Can Run In Parallel**: NO
  - **Parallel Group**: Wave 3 (最后)
  - **Blocks**: None
  - **Blocked By**: Task 9

  **References**:
  - 各测试论文的 arXiv 页面

  **Acceptance Criteria**:
  ```bash
  # 运行集成测试
  pytest tests/integration/ -v --timeout=300
  
  # Assert: ≥7/10 论文编译成功
  # Assert: 所有成功的 PDF 页数 > 0
  
  # 检查文档
  ls docs/
  # Assert: 包含所有必需文档
  
  # 检查 README
  grep "Quick Start" README.md
  # Assert: README 包含快速开始部分
  ```

  **Commit**: YES
  - Message: `docs: add user documentation and integration tests`
  - Files: `README.md`, `docs/*.md`, `tests/integration/*.py`
  - Pre-commit: `pytest tests/ -v`

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 0 | `chore: add assumption validation script` | `scripts/` | 手动运行脚本 |
| 1 | `feat: initialize project structure` | `pyproject.toml`, `src/` | `pip install -e .` |
| 2 | `feat(downloader): implement arXiv download` | `src/ieeet/downloader/` | `pytest tests/test_downloader.py` |
| 3 | `feat(rules): implement config and glossary` | `src/ieeet/rules/` | `pytest tests/test_rules.py` |
| 4 | `feat(translator): implement LLM providers` | `src/ieeet/translator/` | `pytest tests/test_translator.py` |
| 5 | `feat(parser): implement LaTeX parser` | `src/ieeet/parser/` | `pytest tests/test_parser.py` |
| 6 | `feat(translator): implement pipeline` | `src/ieeet/translator/pipeline.py` | `pytest tests/test_pipeline.py` |
| 7 | `feat(validator): implement validation engine` | `src/ieeet/validator/` | `pytest tests/test_validator.py` |
| 8 | `feat(compiler): implement LaTeX compiler` | `src/ieeet/compiler/` | `pytest tests/test_compiler.py` |
| 9 | `feat(cli): implement CLI interface` | `src/ieeet/cli.py` | `ieeet --help` |
| 10 | `docs: add documentation and integration tests` | `README.md`, `docs/` | `pytest tests/integration/` |

---

## Success Criteria

### Verification Commands
```bash
# 端到端测试
ieeet translate https://arxiv.org/abs/2301.07041 --output ./final.pdf

# 检查输出
pdfinfo ./final.pdf | grep Pages
# Expected: Pages: >0

# 运行全部测试
pytest tests/ -v --cov=ieeet
# Expected: 覆盖率 >70%, 所有测试通过
```

### Final Checklist
- [ ] 所有 "Must Have" 功能已实现
- [ ] 所有 "Must NOT Have" 功能未实现
- [ ] 10 篇测试论文中 ≥7 篇编译成功
- [ ] 用户可通过 YAML 添加词表和规则
- [ ] 失败时提供清晰的错误诊断
- [ ] 用户文档完整

---

## Known Limitations (已知限制)

> 以下内容将在 Task 10 中记录到 `docs/known-limitations.md`:

1. **不支持 PDF-only 论文**: 仅支持有 LaTeX 源码的 arXiv 论文
2. **不支持所有 LaTeX 包**: 某些特殊包可能导致编译失败
3. **字体依赖**: 需要系统安装 Noto CJK 字体
4. **翻译质量**: 依赖 LLM 能力，复杂公式上下文可能翻译不准确
5. **速率限制**: arXiv 下载有 3 秒延迟限制
