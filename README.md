# ieeA - arXiv 论文翻译工具

将英文 arXiv 论文翻译成中文，保留数学公式、引用和文档结构。

## 快速开始

```bash
# 安装
pip install -e .

# 翻译 arXiv 论文
ieeA translate https://arxiv.org/abs/2301.07041 --output-dir output/
```

### 高级选项

#### 详细日志模式
使用 `--verbose/-v` 标志启用详细控制台输出：
```bash
ieeA translate https://arxiv.org/abs/2301.07041 --verbose
```

#### 日志文件
每次翻译会自动生成结构化日志文件：
- 位置: `output/<arxiv_id>/translation_log_<timestamp>.json`
- 包含: 翻译配置、chunk 详情、批量信息、跳过的内容、耗时统计

#### 批量翻译优化
- 短内容（< 100 字符）会自动批量翻译，减少 API 调用
- 纯占位符内容（如作者信息）会自动跳过翻译

## 翻译流程 (Pipeline)

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  1. 下载    │ -> │  2. 解析    │ -> │  3. 翻译    │ -> │  4. 重组    │ -> │  5. 编译    │
│  arXiv源码  │    │  LaTeX结构  │    │  文本块     │    │  LaTeX文档  │    │  生成PDF   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 1. 下载 (Downloader)
从 arXiv 下载论文源码压缩包，自动解压并定位主 `.tex` 文件。

### 2. 解析 (Parser)
将 LaTeX 文档解析为可翻译的文本块 (Chunk)，同时保护不应翻译的元素。

#### Chunk 划分依据

| 类型 | 处理方式 | 示例 |
|------|----------|------|
| **保护环境** | 替换为占位符，不翻译 | `equation`, `align`, `tikzpicture`, `verbatim` |
| **可翻译环境** | 整体提取为一个 Chunk | `abstract`, `itemize`, `enumerate` |
| **结构命令** | 提取参数内容为 Chunk | `\title{}`, `\section{}`, `\caption{}` |
| **保护命令** | 替换为占位符，不翻译 | `\cite{}`, `\ref{}`, `\label{}`, `$...$` |
| **段落文本** | 按空行分割，长度>20字符的段落作为 Chunk | 正文段落 |

#### 处理顺序
```
原文 -> 提取标题 -> 提取caption -> 保护数学环境 -> 保护行内公式 
     -> 保护命令(\cite等) -> 提取可翻译环境 -> 分割段落 -> Chunks
```

### 3. 翻译 (Translator)
- 并发调用 LLM API 翻译各 Chunk
- 支持术语表 (Glossary) 保持术语一致性
- 自动重试和断点续传

### 4. 重组 (Reconstructor)
将翻译后的文本替换回占位符位置，还原完整 LaTeX 文档。

### 5. 编译 (Compiler)
使用 XeLaTeX 编译生成中文 PDF，自动注入中文字体支持。

## 配置

配置文件位置：`~/.ieeA/config.yaml`

完整配置模板（按需删减，留空表示使用默认值）：

```yaml
llm:
  # SDK: openai | anthropic | null（null 表示直连 HTTP）
  sdk: null
  # 模型名或列表（列表时取第一个）
  models: openai/gpt-5-mini
  # API Key（当 sdk 非空时必填）
  key: ""
  # 可选：自定义接口地址
  endpoint: https://openrouter.ai/api/v1/chat/completions
  temperature: 0.1
  max_tokens: 4000

compilation:
  engine: xelatex
  timeout: 120
  clean_aux: true

paths:
  output_dir: output
  cache_dir: .cache

fonts:
  # 自动检测中文字体
  auto_detect: true
  # 手动指定字体（可选）
  main: null
  sans: null
  mono: null

translation:
  # 自定义提示词（可选）
  custom_system_prompt: null
  custom_user_prompt: null
  # 额外保留原文的术语列表（不翻译）
  preserve_terms: []
  # 翻译质量：standard 或 high
  quality_mode: standard
  # Few-shot 示例文件路径（可选）
  examples_path: null

parser:
  # 额外保护的 LaTeX 环境（不翻译）
  extra_protected_environments: []
  # 额外可翻译的 LaTeX 环境
  extra_translatable_environments: []
```

### 术语表

术语表位置：`~/.ieeA/glossary.yaml`

```yaml
# 保持原文不翻译
"MMLU": "MMLU"
"LLaMA": "LLaMA"

# 指定翻译
"Attention": "注意力机制"
"Transformer":
  target: "Transformer"
  context: "Deep Learning"
```

## 支持的 LLM

| 提供商 | 模型示例 | 环境变量 |
|--------|----------|----------|
| OpenAI | gpt-4o, gpt-4o-mini | `OPENAI_API_KEY` |
| Claude | claude-3-opus, claude-3-sonnet | `ANTHROPIC_API_KEY` |
| Qwen | qwen-turbo, qwen-max | `DASHSCOPE_API_KEY` |
| Doubao | doubao-pro-* | `VOLCENGINE_API_KEY` |

**提示**：可通过 `base_url` 配置使用 OpenRouter 等代理服务。

## 项目结构

```
src/ieeA/
├── cli.py              # 命令行入口
├── downloader/         # arXiv 下载器
├── parser/             # LaTeX 解析与分块
│   ├── latex_parser.py # 核心解析逻辑
│   └── structure.py    # Chunk 数据结构
├── translator/         # 翻译流水线
├── compiler/           # PDF 编译
├── validator/          # 翻译质量验证
└── rules/              # 配置与术语表
```

## 依赖

- Python 3.10+
- XeLaTeX（用于 PDF 编译）
- 中文字体（macOS 自动检测 Songti SC / PingFang SC）

## License

GPL-3.0
