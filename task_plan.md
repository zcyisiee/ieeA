# Task Plan: ieeA 配置模板整理

## Goal
在 README 中新增完整配置模板，并同步 `docs/configuration.md`。

## Current Phase
Phase 5

## Phases

### Phase 1: 需求与发现
- [x] 读取现有代码与配置路径
- [x] 记录可配置项与默认值来源
- [x] 记录到 findings.md
- **Status:** complete

### Phase 2: 结构与计划
- [x] 确定 README 放置位置与格式
- [x] 明确模板字段与说明格式
- **Status:** complete

### Phase 3: 实现
- [x] 草拟配置模板与中文说明
- [x] 写入 README
- [x] 同步 docs/configuration.md
- **Status:** complete

### Phase 4: 验证
- [x] 对比代码与 README 模板一致性
- [x] lsp_diagnostics 检查（.md 无 LSP 服务器）
- **Status:** complete

### Phase 5: 交付
- [x] 回顾变更文件
- [x] 向用户交付结果
- **Status:** complete

## Key Questions
1. 配置文件格式与读取逻辑在哪里定义？
2. 哪些参数支持 ~/.ieeA 覆盖？

## Decisions Made
| Decision | Rationale |
|----------|-----------|
| README 新增“配置模板”小节 | 用户明确要求放在 README |

## Errors Encountered
| Error | Attempt | Resolution |
|-------|---------|------------|
| session-catchup 路径错误 | 1 | 改用绝对路径执行脚本 |
| No LSP server configured for .md | 1 | 记录为无法执行 LSP 校验 |
