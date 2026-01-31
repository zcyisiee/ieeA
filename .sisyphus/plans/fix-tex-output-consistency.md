# 修复 TEX 输出一致性

## TL;DR

> **Quick Summary**: 确保保存的 `main_translated.tex` 就是实际编译的版本
> 
> **Deliverables**:
> - 修复 cli.py 中的保存逻辑
> - main_translated.tex 包含完整的中文支持配置
> 
> **Estimated Effort**: Quick
> **Critical Path**: Task 1 → Task 2

---

## 问题分析

### 当前问题
`cli.py` 的流程：
1. 保存翻译后的 tex 到 `main_translated.tex`（第 188 行）
2. 编译前重新读取并注入中文支持（第 222-224 行）
3. 编译使用修改后的版本，但**没有回写到文件**

导致：`main_translated.tex` 缺少中文支持配置，与实际编译的版本不一致。

### 修复方案
在编译前，将注入中文支持后的版本**回写**到 `main_translated.tex`。

---

## TODOs

### Task 1: 修复 cli.py 保存逻辑

**修改文件**: `src/ieeet/cli.py`

**修改内容**:
在第 224 行后添加回写逻辑：
```python
latex_source = compiler.inject_chinese_support(latex_source)
# Save the final version that will be compiled
out_file.write_text(latex_source, encoding="utf-8")
```

**验证命令**:
```bash
# 重新翻译后检查 main_translated.tex 是否包含字体配置
grep "setCJKmainfont" output/2601.19778/2601.19778/main_translated.tex
```

**Git 提交**: `修复(cli): 保存编译用的最终版本到main_translated.tex`

---

### Task 2: 验证修复

**验证步骤**:
1. 删除旧的翻译文件
2. 重新运行翻译
3. 检查 main_translated.tex 是否包含字体配置
4. 确认 PDF 正常生成

---

## 成功标准

- [ ] `main_translated.tex` 包含 `\setCJKmainfont{Songti SC}`
- [ ] PDF 正常编译
- [ ] 用户可以直接用 `main_translated.tex` 手动编译得到相同结果
