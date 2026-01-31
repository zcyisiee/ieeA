# 修复嵌套环境保护问题

## TL;DR

> **Quick Summary**: 修复 table/figure 内部的 tabular 被重复保护导致占位符错乱的问题
> 
> **Deliverables**:
> - 移除 tabular/array 从 PROTECTED_ENVIRONMENTS（它们已在 table 内）
> - 确保 table/figure 作为整体保护
> 
> **Estimated Effort**: Quick
> **Critical Path**: Task 1 → Task 2

---

## 问题分析

### 当前问题

1. `PROTECTED_ENVIRONMENTS` 包含：
   - `table`, `table*` (外层环境)
   - `tabular`, `tabular*`, `array` (内层环境)
   
2. 当处理 `\begin{table}...\begin{tabular}...\end{tabular}...\end{table}` 时：
   - `table` 被匹配并创建占位符 `[[MATHENV_N]]`
   - 但 `tabular` 也被匹配，在 table 内部又创建了另一个占位符
   - 导致嵌套保护和占位符编号错乱

3. 结果：`[[MATHENV_7]]` 在 body_template 中存在，但其 preserved_elements 映射指向了错误的内容

### 解决方案

从 `PROTECTED_ENVIRONMENTS` 中移除 `tabular`、`tabular*`、`array`，因为：
- 它们通常在 `table` 环境内部
- `table` 已经作为整体被保护
- 不需要单独保护 tabular

---

## TODOs

### Task 1: 修改 PROTECTED_ENVIRONMENTS

**修改文件**: `src/ieet/parser/latex_parser.py`

**修改内容**:
从 `PROTECTED_ENVIRONMENTS` 中移除 `tabular`、`tabular*`、`array`：

```python
PROTECTED_ENVIRONMENTS = {
    # 数学环境
    "equation", "align", "gather", "split", "eqnarray", "multline",
    "equation*", "align*", "gather*", "eqnarray*", "multline*",
    # 代码
    "tikzpicture", "lstlisting", "verbatim", "minted",
    # 浮动环境（包含 tabular/caption）
    "figure", "figure*", "table", "table*",
    # 注意：tabular/array 不单独保护，因为它们在 table 内部
}
```

**验证命令**:
```bash
python3 -c "
from ieet.parser.latex_parser import LaTeXParser
envs = LaTeXParser.PROTECTED_ENVIRONMENTS
print('tabular in PROTECTED:', 'tabular' in envs)
print('table in PROTECTED:', 'table' in envs)
"
```

**Git 提交**: `修复(parser): 移除tabular单独保护避免嵌套冲突`

---

### Task 2: 验证修复

**验证步骤**:
1. 删除旧的翻译文件
2. 重新翻译 2308.01284
3. 检查 table 内容是否正确显示
4. 检查 PDF 中 table 是否完整

**验证命令**:
```bash
rm -rf output/2308.01284
ieet translate https://arxiv.org/abs/2308.01284 --output-dir output/

# 检查翻译后的文件
grep -A5 "begin{table}" output/2308.01284/main_translated.tex | head -20
grep "MATHENV" output/2308.01284/main_translated.tex  # 应该没有残留占位符
```

---

## 成功标准

- [ ] `tabular` 不在 `PROTECTED_ENVIRONMENTS` 中
- [ ] `table` 仍在 `PROTECTED_ENVIRONMENTS` 中
- [ ] 翻译后的 `main_translated.tex` 中没有 `[[MATHENV_` 占位符残留
- [ ] PDF 中 table 内容完整显示
