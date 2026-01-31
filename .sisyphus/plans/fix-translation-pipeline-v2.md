# 修复 LaTeX 翻译 Pipeline v2

## TL;DR

> **Quick Summary**: 修复翻译 pipeline 的字体配置、环境保护和编译问题，确保中文正确显示
> 
> **Deliverables**:
> - 修复字体配置，支持用户 YAML 自定义，使用系统可用字体
> - 添加列表环境保护 (itemize/enumerate/description)
> - 修复 figure/table 环境只翻译 caption
> - 修复 parser 中硬编码的字体问题
> 
> **Estimated Effort**: Medium
> **Critical Path**: Task 1 → Task 2 → Task 3 → Task 4 → Task 5

---

## 问题分析

### 问题 1: 字体找不到（核心问题）
```
! Package fontspec Error: The font "Noto Serif CJK SC" cannot be found.
Missing character: There is no 基 (U+57FA) in font [lmroman17-regular]
```
- **原因**: `latex_parser.py` 中 `_inject_chinese_support` 硬编码了 Noto 字体
- **系统可用字体**: STSong, STHeiti, STKaiti, STFangsong, Hiragino Sans GB

### 问题 2: 环境保护不完整
- 列表环境 (itemize/enumerate/description) 未保护
- figure/table 环境应只翻译 caption

### 问题 3: 中文不显示
- 因字体找不到导致所有中文字符无法渲染

---

## 系统环境

- **TeX 发行版**: TeX Live 2023
- **引擎**: XeTeX 3.141592653-2.6-0.999995
- **路径**: /Library/TeX/texbin/xelatex
- **可用中文字体**: STSong, STHeiti, STKaiti, STFangsong, Hiragino Sans GB

---

## TODOs

### Task 1: 修复 latex_parser.py 中硬编码的字体

**问题**: `_inject_chinese_support` 方法硬编码了 Noto 字体，但系统没有安装

**修改文件**: `src/ieeet/parser/latex_parser.py`

**修改内容**:
将 `_inject_chinese_support` 方法改为使用 `chinese_support.py` 中的自动检测功能：

```python
def _inject_chinese_support(self, preamble: str) -> str:
    from ..compiler.chinese_support import inject_chinese_support
    return inject_chinese_support(preamble)
```

**验证命令**:
```bash
python3 -c "
from ieeet.parser.latex_parser import LaTeXParser
import tempfile

latex = r'\documentclass{article}\begin{document}测试\end{document}'
with tempfile.NamedTemporaryFile(mode='w', suffix='.tex', delete=False) as f:
    f.write(latex)
    path = f.name

parser = LaTeXParser()
doc = parser.parse_file(path)
result = doc.reconstruct()
print('使用的字体:', [l for l in result.split('\n') if 'setCJKmainfont' in l])
"
```

**Git 提交**: `修复(parser): 使用自动检测字体替代硬编码`

---

### Task 2: 添加列表环境保护

**问题**: itemize/enumerate/description 环境内容被错误翻译

**修改文件**: `src/ieeet/parser/latex_parser.py`

**修改内容**:
在 `PROTECTED_ENVIRONMENTS` 中添加列表环境：

```python
PROTECTED_ENVIRONMENTS = {
    # 数学环境
    "equation", "align", "gather", "split", "eqnarray", "multline",
    "equation*", "align*", "gather*", "eqnarray*", "multline*",
    # 代码和图形
    "tikzpicture", "lstlisting", "verbatim", "minted",
    # 列表环境 (新增)
    "itemize", "enumerate", "description",
    # 表格环境 (新增)
    "tabular", "tabular*", "array",
}
```

**验证命令**:
```bash
python3 -c "
from ieeet.parser.latex_parser import LaTeXParser
print('itemize protected:', 'itemize' in LaTeXParser.PROTECTED_ENVIRONMENTS)
print('enumerate protected:', 'enumerate' in LaTeXParser.PROTECTED_ENVIRONMENTS)
"
```

**Git 提交**: `修复(parser): 添加列表和表格环境保护`

---

### Task 3: 修复 figure/table 环境只翻译 caption

**问题**: figure/table 环境应该保护整体结构，只翻译 caption

**修改文件**: `src/ieeet/parser/latex_parser.py`

**修改内容**:
1. 将 `figure` 和 `table` 添加到 `PROTECTED_ENVIRONMENTS`
2. 在保护这些环境后，单独提取其中的 `\caption{...}` 作为可翻译 chunk

添加新方法 `_protect_float_environments`:
```python
def _protect_float_environments(self, text: str) -> str:
    """保护 figure/table 环境，但提取 caption 用于翻译"""
    for env in ["figure", "figure*", "table", "table*"]:
        pattern = re.compile(
            r"(\\begin\{" + env + r"\}.*?\\end\{" + env + r"\})",
            re.DOTALL
        )
        text = self._replace_with_placeholder(text, pattern, env.upper().replace("*", "STAR"))
    return text
```

**验证命令**:
```bash
python3 -c "
from ieeet.parser.latex_parser import LaTeXParser
print('figure protected:', 'figure' in LaTeXParser.PROTECTED_ENVIRONMENTS)
print('table protected:', 'table' in LaTeXParser.PROTECTED_ENVIRONMENTS)
"
```

**Git 提交**: `修复(parser): 保护figure/table环境结构`

---

### Task 4: 更新用户配置示例

**问题**: 用户需要能够通过 YAML 配置自定义字体

**修改文件**: `~/.ieeet/config.yaml` (用户配置示例)

**配置示例**:
```yaml
fonts:
  main: "STSong"           # 宋体 - 正文
  sans: "STHeiti"          # 黑体 - 标题
  mono: "STFangsong"       # 仿宋 - 代码
  auto_detect: false       # 禁用自动检测，使用指定字体
```

**验证命令**:
```bash
python3 -c "
from ieeet.rules.config import load_config
config = load_config()
print('字体配置:', config.fonts)
"
```

**Git 提交**: 无需提交（用户配置文件）

---

### Task 5: 完整编译测试

**验证步骤**:
1. 删除旧的翻译文件
2. 重新运行翻译
3. 验证 PDF 中文正确显示
4. 验证环境保护正确

**验证命令**:
```bash
# 1. 清理旧文件
rm -f output/2601.19778/main_translated.tex output/2601.19778/translation_state.json

# 2. 重新翻译
ieeet translate 2601.19778 --output-dir output/

# 3. 验证编译无字体错误
xelatex -interaction=nonstopmode output/2601.19778/main_translated.tex 2>&1 | grep -c "font.*cannot be found"
# 期望: 0

# 4. 打开 PDF 验证中文显示
open output/2601.19778/2601.19778.pdf
```

**成功标准**:
- [ ] 编译无字体错误
- [ ] PDF 中文正确显示
- [ ] 列表环境未被翻译
- [ ] figure/table 结构完整

**Git 提交**: `测试: 验证翻译pipeline修复完成`

---

## 执行顺序

| 序号 | 任务 | 依赖 |
|------|------|------|
| 1 | 修复硬编码字体 | 无 |
| 2 | 添加列表环境保护 | Task 1 |
| 3 | 修复 figure/table | Task 2 |
| 4 | 更新用户配置 | Task 1 |
| 5 | 完整编译测试 | Task 1-4 |

---

## 成功标准

- [ ] `xelatex` 编译无 "font cannot be found" 错误
- [ ] PDF 中所有中文正确显示
- [ ] itemize/enumerate/description 环境内容未被翻译
- [ ] figure/table 环境结构完整，仅 caption 被翻译
- [ ] 用户可通过 `~/.ieeet/config.yaml` 自定义字体
