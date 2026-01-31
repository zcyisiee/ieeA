# 修复 LaTeX 翻译 Pipeline

## TL;DR

> **Quick Summary**: 修复 ieeT 翻译 pipeline 中的四个关键问题：占位符还原失败、字体配置错误、作者信息被翻译、缺少 bibtex 编译
> 
> **Deliverables**:
> - 修复 `structure.py` 中的占位符还原逻辑
> - 扩展 `config.py` 支持用户 YAML 自定义字体配置
> - 修复 `latex_parser.py` 中的作者块保护（支持 IEEE 格式）
> - 修复 `latex_compiler.py` 添加 bibtex/biber 编译流程
> 
> **Estimated Effort**: Medium
> **Parallel Execution**: NO - sequential (有依赖关系)
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5

---

## Context

### Original Request
修复 ieeT 翻译 pipeline 使其能正确输出翻译后的 tex 文件，确保：
1. 作者等相关信息不翻译
2. xeCJK 字体正确配置（支持用户 YAML 自定义）
3. `[[LABEL_55]]` 等占位符被正确还原
4. 添加 bibtex 编译支持

### 问题分析

**问题1: 占位符未还原 (CRITICAL)**
- 文件: `src/ieeet/parser/structure.py`
- 根因: `reconstruct()` 方法只替换 `{{CHUNK_uuid}}` 格式占位符，未处理 `[[LABEL_xx]]`, `[[CITE_xx]]`, `[[MATH_xx]]` 等直接嵌入 body_template 的占位符
- 这些占位符存储在 `Chunk.preserved_elements` 中但未被还原

**问题2: 字体配置问题**
- 文件: `src/ieeet/rules/config.py`, `src/ieeet/defaults/config.yaml`, `src/ieeet/compiler/chinese_support.py`
- 根因: 硬编码 Noto 字体，但 macOS 上可能没有安装
- 解决: 支持用户通过 `~/.ieeet/config.yaml` 自定义字体 + 自动检测可用字体

**问题3: 作者信息被翻译**
- 文件: `src/ieeet/parser/latex_parser.py`
- 根因: `\author` 块未被保护，被当作可翻译段落处理
- 注意: IEEE 论文使用 `\IEEEauthorblockN{...}` 和 `\IEEEauthorblockA{...}` 嵌套格式

**问题4: 缺少 bibtex 编译**
- 文件: `src/ieeet/compiler/latex_compiler.py`
- 根因: 只运行一次 xelatex，缺少 bibtex 步骤和多次编译
- 注意: 需检测 biblatex 并使用 biber 代替 bibtex

---

## Metis Gap Analysis 响应

### 已确认的关键决策
1. **占位符修复策略**: 在 `reconstruct()` 添加第二遍还原循环，不改变创建逻辑
2. **作者块保护**: 保护整个 `\author{...}` 块（包括 IEEE 嵌套格式），`\title` 保持翻译
3. **字体配置优先级**: 用户配置 > 自动检测 > 硬编码默认值
4. **bibtex 触发条件**: 仅当检测到 `\bibliography` 或 `\bibliographystyle` 时运行

### 边界情况处理
- 用户配置的字体不存在时: 输出警告，继续使用（让 xelatex 报错）
- 检测到 `\usepackage{biblatex}`: 使用 biber 而非 bibtex
- 嵌套占位符: 内层先还原，外层后还原（通过遍历顺序保证）

---

## Work Objectives

### Core Objective
修复翻译 pipeline 使其能正确生成可编译的中文 LaTeX 文档

### Concrete Deliverables
- `structure.py`: 正确还原所有占位符
- `config.py` + `config.yaml`: 添加 FontConfig 支持用户自定义
- `chinese_support.py`: 使用配置的字体 + 自动检测
- `latex_parser.py`: 保护作者块（支持 IEEE 格式嵌套）
- `latex_compiler.py`: 完整的 xelatex + bibtex/biber 编译流程

### Definition of Done
- [ ] `ieeet translate` 命令生成的 tex 文件无 `[[LABEL_xx]]` 等残留占位符
- [ ] 生成的 tex 文件包含正确的 CJK 字体配置
- [ ] 用户可通过 `~/.ieeet/config.yaml` 自定义字体
- [ ] 作者信息保持英文原文（包括 IEEE 格式）
- [ ] PDF 正确生成，包含参考文献

### Must Have (Guardrails)
- 使用现有 `_protect_commands()` 模式实现作者保护
- FontConfig 遵循现有 Pydantic 模式（可选字段，默认 None）
- bibtex 失败不阻止编译（警告但继续）
- 每个文件修改后运行 `pytest`

### Must NOT Have (Guardrails)
- 不要翻译 `\author` 块内容
- 不要翻译 `\bibliography` 相关内容
- 不要改变现有占位符格式 `[[PREFIX_N]]`
- 不要修改 `chunker.py`（不在范围内）
- 不要添加新的 pip 依赖
- 不要让字体配置成为必填项

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO (无现成测试)
- **User wants tests**: Manual verification
- **QA approach**: 手动验证 + 命令行测试

---

## TODOs

### Task 1: 修复占位符还原逻辑

**What to do**:

修改 `src/ieeet/parser/structure.py` 中的 `LaTeXDocument.reconstruct()` 方法：

```python
def reconstruct(self, translated_chunks: Optional[Dict[str, str]] = None) -> str:
    """
    Reconstructs the full document.

    Args:
        translated_chunks: Dict mapping chunk ID to translated text.
    """
    if self.body_template:
        result = self.body_template
        
        # First pass: Replace {{CHUNK_uuid}} placeholders with translated content
        for chunk in self.chunks:
            placeholder = f"{{{{CHUNK_{chunk.id}}}}}"
            if placeholder in result:
                trans_text = (
                    translated_chunks.get(chunk.id) if translated_chunks else None
                )
                reconstructed = chunk.reconstruct(trans_text)
                result = result.replace(placeholder, reconstructed)
        
        # Second pass: Restore ALL preserved elements (LABEL, CITE, MATH, etc.)
        # These are stored as chunks with preserved_elements mapping
        for chunk in self.chunks:
            for placeholder, original in chunk.preserved_elements.items():
                result = result.replace(placeholder, original)
        
        return self.preamble + result

    body_parts = []
    for chunk in self.chunks:
        trans_text = translated_chunks.get(chunk.id) if translated_chunks else None
        body_parts.append(chunk.reconstruct(trans_text))

    return self.preamble + "".join(body_parts)
```

**Must NOT do**:
- 不要改变 chunk 的存储方式
- 不要修改 `Chunk.reconstruct()` 方法

**References**:
- `src/ieeet/parser/structure.py:48-71` - 当前 reconstruct 实现
- `src/ieeet/parser/latex_parser.py:137-154` - `_replace_with_placeholder` 创建占位符的逻辑

**Acceptance Criteria**:
```bash
# 验证命令
grep -c '\[\[LABEL_' output/2601.19778/main_translated.tex
# 期望: 0 (无残留占位符)

grep -c '\[\[CITE_' output/2601.19778/main_translated.tex  
# 期望: 0

grep -c '\[\[MATH_' output/2601.19778/main_translated.tex
# 期望: 0

grep -c '\\label{' output/2601.19778/main_translated.tex
# 期望: >=2 (有 label 命令)
```

**Commit**: YES
- Message: `fix(parser): restore all placeholder types in document reconstruction`
- Files: `src/ieeet/parser/structure.py`

---

### Task 2: 修复字体配置 - 支持用户 YAML 配置 + 自动检测

**What to do**:

#### 2.1 扩展配置模型 `src/ieeet/rules/config.py`

添加字体配置到 Config 模型：

```python
class FontConfig(BaseModel):
    """CJK font configuration."""
    main: Optional[str] = None      # 主字体 (宋体类)
    sans: Optional[str] = None      # 无衬线字体 (黑体类)  
    mono: Optional[str] = None      # 等宽字体
    auto_detect: bool = True        # 是否自动检测可用字体

class Config(BaseModel):
    llm: LLMConfig = Field(default_factory=LLMConfig)
    compilation: CompilationConfig = Field(default_factory=CompilationConfig)
    paths: PathsConfig = Field(default_factory=PathsConfig)
    fonts: FontConfig = Field(default_factory=FontConfig)  # NEW
```

#### 2.2 更新默认配置 `src/ieeet/defaults/config.yaml`

```yaml
llm:
  provider: openai
  model: gpt-4o-mini
  api_key_env: OPENAI_API_KEY
  temperature: 0.1
  max_tokens: 4000

compilation:
  engine: xelatex
  timeout: 120
  clean_aux: true

paths:
  output_dir: output
  cache_dir: .cache

# NEW: Font configuration
fonts:
  # User can specify fonts directly:
  # main: "Songti SC"
  # sans: "PingFang SC"
  # mono: "Menlo"
  
  # Or let the system auto-detect available fonts
  auto_detect: true
```

#### 2.3 更新字体检测 `src/ieeet/compiler/chinese_support.py`

```python
import subprocess
import re
from typing import Optional, Dict

# 按优先级排序的中文字体列表
CJK_FONT_CANDIDATES = {
    "main": [
        "Noto Serif CJK SC",
        "Source Han Serif SC", 
        "STSong",
        "Songti SC",
        "PingFang SC",
    ],
    "sans": [
        "Noto Sans CJK SC",
        "Source Han Sans SC",
        "STHeiti",
        "Heiti SC", 
        "PingFang SC",
    ],
    "mono": [
        "Noto Sans Mono CJK SC",
        "Source Han Mono SC",
        "STFangsong",
        "PingFang SC",
    ],
}

def get_available_fonts() -> set:
    """Get set of available font family names on the system."""
    try:
        result = subprocess.run(
            ["fc-list", ":lang=zh", "family"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode == 0:
            fonts = set()
            for line in result.stdout.strip().split("\n"):
                for name in line.split(","):
                    fonts.add(name.strip())
            return fonts
    except Exception:
        pass
    return set()

def detect_cjk_fonts() -> Dict[str, str]:
    """Detect available CJK fonts and return best matches."""
    available = get_available_fonts()
    result = {}
    
    for font_type, candidates in CJK_FONT_CANDIDATES.items():
        for font in candidates:
            if font in available:
                result[font_type] = font
                break
        else:
            result[font_type] = candidates[-1]  # Fallback to last (usually PingFang)
    
    return result

def get_fonts_from_config(font_config) -> Dict[str, str]:
    """
    Get fonts from config, with auto-detection fallback.
    
    Args:
        font_config: FontConfig object with main/sans/mono/auto_detect fields
    
    Returns:
        Dict with 'main', 'sans', 'mono' font names
    """
    # Start with auto-detected fonts if enabled
    if font_config.auto_detect:
        fonts = detect_cjk_fonts()
    else:
        fonts = {
            "main": CJK_FONT_CANDIDATES["main"][-1],
            "sans": CJK_FONT_CANDIDATES["sans"][-1],
            "mono": CJK_FONT_CANDIDATES["mono"][-1],
        }
    
    # Override with user-specified fonts
    if font_config.main:
        fonts["main"] = font_config.main
    if font_config.sans:
        fonts["sans"] = font_config.sans
    if font_config.mono:
        fonts["mono"] = font_config.mono
    
    return fonts

def inject_chinese_support(latex_source: str, font_config=None) -> str:
    """
    Injects xeCJK package with configured or detected fonts.
    
    Args:
        latex_source: The LaTeX source code
        font_config: Optional FontConfig object. If None, auto-detect fonts.
    """
    if "xeCJK" in latex_source:
        return latex_source

    # Get fonts from config or auto-detect
    if font_config:
        fonts = get_fonts_from_config(font_config)
    else:
        fonts = detect_cjk_fonts()
    
    injection = (
        "\n% Auto-injected Chinese Support\n"
        r"\usepackage{xeCJK}" + "\n"
        rf"\setCJKmainfont{{{fonts['main']}}}" + "\n"
        rf"\setCJKsansfont{{{fonts['sans']}}}" + "\n"
        rf"\setCJKmonofont{{{fonts['mono']}}}" + "\n"
    )
    
    match = re.search(r'\\documentclass(\[.*?\])?\{.*?\}', latex_source, re.DOTALL)
    
    if match:
        end_pos = match.end()
        return latex_source[:end_pos] + injection + latex_source[end_pos:]
    else:
        return injection + latex_source
```

#### 2.4 更新 CLI 传递配置 `src/ieeet/cli.py`

在编译部分传递 font_config:

```python
# In the compile section (around line 220-230)
latex_source = compiler.inject_chinese_support(latex_source)
# Change to:
from ieeet.rules.config import load_config
config = load_config()
latex_source = inject_chinese_support(latex_source, config.fonts)
```

#### 2.5 同步更新 `src/ieeet/parser/latex_parser.py`

在 `_inject_chinese_support` 方法中也使用配置：

```python
def _inject_chinese_support(self, preamble: str, font_config=None) -> str:
    if "xeCJK" in preamble:
        return preamble

    from ..compiler.chinese_support import get_fonts_from_config, detect_cjk_fonts
    
    if font_config:
        fonts = get_fonts_from_config(font_config)
    else:
        fonts = detect_cjk_fonts()

    injection = (
        "\n% Chinese Support\n"
        "\\usepackage{xeCJK}\n"
        f"\\setCJKmainfont{{{fonts['main']}}}\n"
        f"\\setCJKsansfont{{{fonts['sans']}}}\n"
        f"\\setCJKmonofont{{{fonts['mono']}}}\n"
    )

    match = re.search(r"\\documentclass(\[.*?\])?\{.*?\}", preamble, re.DOTALL)
    if match:
        end_pos = match.end()
        return preamble[:end_pos] + injection + preamble[end_pos:]
    return preamble
```

**用户配置示例** (`~/.ieeet/config.yaml`):

```yaml
# 用户自定义字体配置
fonts:
  main: "Songti SC"        # 衬线字体（正文）
  sans: "PingFang SC"      # 无衬线字体（标题）
  mono: "Menlo"            # 等宽字体（代码）
  auto_detect: false       # 禁用自动检测，使用上面指定的字体
```

**Must NOT do**:
- 不要硬编码单一字体
- 不要在检测失败时抛出异常
- 不要忽略用户的自定义配置

**References**:
- `src/ieeet/compiler/chinese_support.py:1-44` - 当前实现
- `src/ieeet/parser/latex_parser.py:72-88` - parser 中的字体注入
- `fc-list :lang=zh family` 输出显示系统有 `PingFang SC`, `STHeiti`, `Kaiti SC` 等

**Acceptance Criteria**:
```bash
# 验证字体配置不再被注释
grep 'setCJKmainfont' output/2601.19778/main_translated.tex | grep -v '^%'
# 期望: 有一行未被注释的 setCJKmainfont

# 验证使用的是系统存在的字体
python3 -c "
import subprocess
result = subprocess.run(['fc-list', ':lang=zh', 'family'], capture_output=True, text=True)
fonts = set(f.strip() for line in result.stdout.split('\n') for f in line.split(','))
print('PingFang SC' in fonts or 'STHeiti' in fonts)
"
# 期望: True
```

**Commit**: YES
- Message: `fix(compiler): auto-detect available CJK fonts for Chinese support`
- Files: `src/ieeet/compiler/chinese_support.py`, `src/ieeet/parser/latex_parser.py`

---

### Task 3: 保护作者信息不被翻译（支持 IEEE 格式）

**What to do**:

修改 `src/ieeet/parser/latex_parser.py`，添加 `_protect_author_block()` 方法处理带嵌套括号的作者块：

```python
def _protect_author_block(self, text: str) -> str:
    """
    Protect the entire \\author{...} block from translation.
    Uses balanced brace matching to handle nested IEEE author macros like:
    \\author{\\IEEEauthorblockN{Name}\\IEEEauthorblockA{Affiliation}}
    """
    pattern = re.compile(r'(\\author\s*\{)', re.DOTALL)
    
    result = []
    pos = 0
    
    for match in pattern.finditer(text):
        result.append(text[pos:match.start()])
        
        # Find matching closing brace using balanced bracket counting
        start = match.end()
        brace_count = 1
        i = start
        while i < len(text) and brace_count > 0:
            if text[i] == '{':
                brace_count += 1
            elif text[i] == '}':
                brace_count -= 1
            i += 1
        
        # Extract full author block including nested content
        full_block = match.group(0) + text[start:i]
        
        # Create placeholder
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
    
    result.append(text[pos:])
    return ''.join(result)
```

在 `_process_body` 方法中，在其他保护之前调用：

```python
def _process_body(self, body: str) -> str:
    result = body

    # Protect author block FIRST (before other processing)
    # This handles IEEE nested format: \author{\IEEEauthorblockN{...}\IEEEauthorblockA{...}}
    result = self._protect_author_block(result)
    
    result = self._protect_math_environments(result)
    result = self._protect_inline_math(result)
    result = self._protect_commands(result)
    result = self._extract_translatable_content(result)

    return result
```

**Must NOT do**:
- 不要只保护作者姓名，要保护整个 `\author{...}` 块及其所有嵌套内容
- 不要使用简单正则（无法处理嵌套括号）
- 不要破坏现有的其他保护逻辑
- 不要修改 `\title` 处理（它应该被翻译）

**References**:
- `src/ieeet/parser/latex_parser.py:90-98` - `_process_body` 方法
- `src/ieeet/parser/latex_parser.py:121-135` - `_protect_commands` 方法模式

**IEEE 作者块格式示例** (内联):
```latex
\author{
    \IEEEauthorblockN{Ahmad Farooq}
    \IEEEauthorblockA{\textit{University of Arkansas at Little Rock} \\
    Little Rock, Arkansas, USA \\
    afarooq@ualr.edu \\
    ORCID: 0009-0002-3684-5876}
    \and
    \IEEEauthorblockN{Kamran Iqbal}
    \IEEEauthorblockA{\textit{University of Arkansas at Little Rock} \\
    Little Rock, Arkansas, USA \\
    kxiqbal@ualr.edu \\
    ORCID: 0000-0001-8375-290X}
}
```

**Acceptance Criteria**:
```python
# 测试脚本 - 验证作者块保护
from ieeet.parser.latex_parser import LaTeXParser
import re

# 创建测试用 IEEE 格式文档
test_tex = r'''
\documentclass{IEEEtran}
\begin{document}
\author{
    \IEEEauthorblockN{John Smith}
    \IEEEauthorblockA{University of Test\\
    test@example.com}
}
\maketitle
\section{Introduction}
This is content.
\end{document}
'''

# 保存并解析
with open('/tmp/test_author.tex', 'w') as f:
    f.write(test_tex)

parser = LaTeXParser()
doc = parser.parse_file('/tmp/test_author.tex')

# 验证1: 作者内容不在任何可翻译 chunk 中
for chunk in doc.chunks:
    assert 'John Smith' not in chunk.content, f'Author name found in chunk: {chunk.content}'
    assert 'University of Test' not in chunk.content, f'Affiliation found in chunk: {chunk.content}'

# 验证2: 重组后无 [[AUTHOR_xx]] 残留
result = doc.reconstruct()
assert '[[AUTHOR_' not in result, f'AUTHOR placeholder not restored: {result}'

# 验证3: 原始作者块完整保留
assert 'IEEEauthorblockN{John Smith}' in result, 'Author block not preserved'

print('PASS: Author block correctly protected')
```

**Commit**: YES
- Message: `fix(parser): protect author block from translation with IEEE format support`
- Files: `src/ieeet/parser/latex_parser.py`

---

### Task 4: 添加 bibtex/biber 编译支持

**What to do**:

修改 `src/ieeet/compiler/latex_compiler.py`，实现完整的编译流程，支持检测 biblatex 并使用正确的工具：

```python
def _detect_bibliography_tool(self, latex_source: str) -> Optional[str]:
    """Detect which bibliography tool to use based on LaTeX source."""
    # Check for biblatex (requires biber)
    if r'\usepackage{biblatex}' in latex_source or r'\usepackage[' in latex_source and 'biblatex' in latex_source:
        return 'biber'
    # Check for traditional bibliography
    if r'\bibliography{' in latex_source or r'\bibliographystyle{' in latex_source:
        return 'bibtex'
    return None

def _run_engine(
    self, engine: str, source_file: Path, cwd: Path, latex_source: str = ""
) -> Tuple[bool, str, Optional[str]]:
    """Runs a specific latex engine with full compilation cycle."""
    
    all_logs = []
    
    # First pass: latex
    success, log, error = self._run_single_pass(engine, source_file, cwd)
    all_logs.append(f"=== First {engine} pass ===\n{log}")
    if not success and not (cwd / "main.aux").exists():
        return False, "\n".join(all_logs), error
    
    # Detect and run bibliography tool
    bib_tool = self._detect_bibliography_tool(latex_source)
    if bib_tool:
        bib_success, bib_log = self._run_bibliography_tool(bib_tool, cwd)
        all_logs.append(f"=== {bib_tool} pass ===\n{bib_log}")
        if not bib_success:
            all_logs.append(f"Warning: {bib_tool} had issues, continuing...")
    
    # Second pass: latex
    success, log, error = self._run_single_pass(engine, source_file, cwd)
    all_logs.append(f"=== Second {engine} pass ===\n{log}")
    
    # Third pass: latex (to resolve all references)
    success, log, error = self._run_single_pass(engine, source_file, cwd)
    all_logs.append(f"=== Third {engine} pass ===\n{log}")
    
    pdf_file = cwd / "main.pdf"
    if pdf_file.exists():
        return True, "\n".join(all_logs), None
    else:
        return False, "\n".join(all_logs), self._extract_error("\n".join(all_logs))

def _run_single_pass(
    self, engine: str, source_file: Path, cwd: Path
) -> Tuple[bool, str, Optional[str]]:
    """Runs a single pass of the latex engine."""
    cmd = [engine, "-interaction=nonstopmode", source_file.name]

    try:
        process = subprocess.run(
            cmd,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=self.timeout,
            encoding="utf-8",
            errors="replace",
        )

        log_content = process.stdout + "\n" + process.stderr
        log_file = cwd / "main.log"
        if log_file.exists():
            try:
                file_log = log_file.read_text(encoding="utf-8", errors="replace")
                if file_log.strip():
                    log_content = file_log
            except Exception:
                pass

        pdf_file = cwd / "main.pdf"
        if process.returncode == 0 or pdf_file.exists():
            return True, log_content, None
        else:
            return False, log_content, self._extract_error(log_content)

    except subprocess.TimeoutExpired:
        return False, "Timeout expired", "Compilation timed out"
    except Exception as e:
        return False, str(e), str(e)

def _run_bibliography_tool(self, tool: str, cwd: Path) -> Tuple[bool, str]:
    """Runs bibtex or biber on the aux file."""
    tool_cmd = shutil.which(tool)
    if not tool_cmd:
        return False, f"{tool} not found in PATH"
    
    try:
        process = subprocess.run(
            [tool, "main"],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60,
            encoding="utf-8",
            errors="replace",
        )
        log = process.stdout + "\n" + process.stderr
        
        # Check for output file creation as success indicator
        if tool == 'biber':
            success_file = cwd / "main.bbl"
        else:
            success_file = cwd / "main.bbl"
        
        return success_file.exists() or process.returncode == 0, log
    except Exception as e:
        return False, str(e)
```

同时需要修改 `compile()` 方法，将 latex_source 传递给 `_run_engine`:

```python
def compile(
    self,
    latex_source: str,
    output_path: Union[str, Path],
    working_dir: Optional[Union[str, Path]] = None,
) -> CompilationResult:
    # ... existing code ...
    
    for engine in self.engines:
        if not shutil.which(engine):
            continue

        # Pass latex_source for bibliography detection
        success, log, error = self._run_engine(engine, source_file, temp_path, latex_source)
        # ... rest of existing code ...
```

**Must NOT do**:
- 不要删除现有的 fallback 逻辑
- 不要让 bibtex/biber 失败阻止整个编译
- 不要将 bibtex 添加到 `self.engines` 列表（它不是 TeX 引擎）

**References**:
- `src/ieeet/compiler/latex_compiler.py:112-149` - 当前 `_run_engine` 实现
- 标准 LaTeX 编译流程: `xelatex -> bibtex/biber -> xelatex -> xelatex`

**Acceptance Criteria**:
```python
# 测试脚本 - 验证 bibtex 编译
from pathlib import Path
from ieeet.compiler.latex_compiler import LaTeXCompiler

# 创建测试文件
test_dir = Path('/tmp/bibtest')
test_dir.mkdir(exist_ok=True)

(test_dir / 'refs.bib').write_text(r'''
@article{test2020,
  author = {Test Author},
  title = {Test Title},
  journal = {Test Journal},
  year = {2020}
}
''')

tex = r'''
\documentclass{article}
\begin{document}
Citation test~\cite{test2020}.
\bibliography{refs}
\bibliographystyle{plain}
\end{document}
'''

compiler = LaTeXCompiler()
result = compiler.compile(tex, test_dir / 'out.pdf', working_dir=test_dir)

assert result.success, f'Compilation failed: {result.error_message}'
assert 'undefined citation' not in (result.log_content or '').lower(), 'Citations not resolved'
print('PASS: bibtex compilation works')
```

**Commit**: YES
- Message: `fix(compiler): add bibtex/biber compilation for bibliography support`
- Files: `src/ieeet/compiler/latex_compiler.py`

---

### Task 5: 集成测试 - 验证修复后的 Pipeline

**What to do**:

1. 删除现有的翻译状态文件以强制重新翻译：
```bash
rm -f output/2601.19778/translation_state.json
rm -f output/2601.19778/main_translated.tex
```

2. 重新运行翻译（或手动测试重组逻辑）：
```bash
# 如果有 API key 可以完整测试
ieeet translate 2601.19778 --output output/

# 或者只测试重组逻辑（无需 API）
python3 -c "
from ieeet.parser.latex_parser import LaTeXParser
from ieeet.compiler import LaTeXCompiler

# Parse
parser = LaTeXParser()
doc = parser.parse_file('output/2601.19778/output.tex')

# Reconstruct without translation (test placeholder restoration)
result = doc.reconstruct()

# Check for leftover placeholders
import re
labels = re.findall(r'\[\[LABEL_\d+\]\]', result)
cites = re.findall(r'\[\[CITE_\d+\]\]', result)
maths = re.findall(r'\[\[MATH_\d+\]\]', result)

print(f'Leftover LABEL placeholders: {len(labels)}')
print(f'Leftover CITE placeholders: {len(cites)}')
print(f'Leftover MATH placeholders: {len(maths)}')

# Should all be 0
assert len(labels) == 0, 'LABEL placeholders not restored!'
assert len(cites) == 0, 'CITE placeholders not restored!'
assert len(maths) == 0, 'MATH placeholders not restored!'

print('All placeholders correctly restored!')
"
```

3. 验证编译：
```bash
cd output/2601.19778
xelatex -interaction=nonstopmode main_translated.tex
bibtex main_translated
xelatex -interaction=nonstopmode main_translated.tex
xelatex -interaction=nonstopmode main_translated.tex

# 检查 PDF 生成
ls -la main_translated.pdf
```

**Must NOT do**:
- 不要跳过验证步骤
- 不要在有错误时继续

**Acceptance Criteria**:
```bash
# 完整验证清单
echo "=== Checking placeholder restoration ==="
grep -c '\[\[LABEL_' output/2601.19778/main_translated.tex && echo "FAIL: LABEL残留" || echo "PASS"
grep -c '\[\[CITE_' output/2601.19778/main_translated.tex && echo "FAIL: CITE残留" || echo "PASS"
grep -c '\[\[MATH_' output/2601.19778/main_translated.tex && echo "FAIL: MATH残留" || echo "PASS"

echo "=== Checking font configuration ==="
grep 'setCJKmainfont' output/2601.19778/main_translated.tex | grep -v '^%' && echo "PASS" || echo "FAIL: 字体被注释"

echo "=== Checking author protection ==="
grep -A2 '\\author{' output/2601.19778/main_translated.tex | grep -q 'University' && echo "PASS" || echo "FAIL: 作者被翻译"

echo "=== Checking PDF generation ==="
test -f output/2601.19778/main_translated.pdf && echo "PASS" || echo "FAIL: PDF未生成"
```

**Commit**: YES
- Message: `test: verify translation pipeline fixes`
- Files: None (验证任务)

---

## Commit Strategy

| After Task | Message | Files | Verification |
|------------|---------|-------|--------------|
| 1 | `fix(parser): restore all placeholder types in document reconstruction` | structure.py | grep 检查无残留占位符 |
| 2 | `fix(compiler): auto-detect available CJK fonts for Chinese support` | chinese_support.py, latex_parser.py | 字体配置未被注释 |
| 3 | `fix(parser): protect author block from translation` | latex_parser.py | 作者信息为英文 |
| 4 | `fix(compiler): add bibtex compilation for bibliography support` | latex_compiler.py | PDF 包含参考文献 |
| 5 | - | - | 完整测试 |

---

## Success Criteria

### Verification Commands
```bash
# 1. 无残留占位符
grep -E '\[\[(LABEL|CITE|MATH|REF|FOOTNOTE|MATHENV)_\d+\]\]' output/2601.19778/main_translated.tex
# 期望: 无输出

# 2. 字体配置正确
grep -E '^\\setCJK' output/2601.19778/main_translated.tex
# 期望: 3行未注释的字体设置

# 3. 作者保持英文  
grep -A10 '\\author{' output/2601.19778/main_translated.tex | grep 'University'
# 期望: 有输出

# 4. PDF 可编译
xelatex -interaction=nonstopmode output/2601.19778/main_translated.tex
# 期望: 无致命错误
```

### Final Checklist
- [ ] 所有 `[[XXX_nn]]` 占位符已还原为原始 LaTeX 命令
- [ ] CJK 字体使用系统可用字体（如 PingFang SC）
- [ ] `\author` 块内容保持英文
- [ ] 编译流程包含 bibtex
- [ ] PDF 正确生成，包含参考文献
