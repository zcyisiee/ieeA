# Findings & Decisions

## Requirements
- 梳理项目配置项
- 生成 ~/.ieeA 可配置参数模板
- 在 README 中用中文简洁说明
- 同步旧文档 `docs/configuration.md`

## Research Findings
- 已读取 planning-with-files 模板（task_plan/findings/progress），用于创建计划文件
- 发现 README 位置：`README.md`
- 发现配置相关文件：`src/ieeA/rules/config.py`、`src/ieeA/defaults/config.yaml`、`docs/configuration.md`
- 默认配置文件 `src/ieeA/defaults/config.yaml` 包含：
  - llm: sdk, models, endpoint, key, temperature, max_tokens
  - compilation: engine, timeout, clean_aux
  - paths: output_dir, cache_dir
  - fonts: auto_detect
  - translation: quality_mode, examples_path
- 配置模型定义 `src/ieeA/rules/config.py` 还支持：
  - llm.models 可为字符串或列表；sdk 仅允许 openai/anthropic/None
  - fonts: main, sans, mono, auto_detect
  - translation: custom_system_prompt, custom_user_prompt, preserve_terms, quality_mode, examples_path
  - parser: extra_protected_environments, extra_translatable_environments
- CLI 会读取 `config.llm.key`，在 sdk 非空时必须提供（可通过 --key 覆盖）。
- 高质量模式会读取 `translation.examples_path` 并加载 few-shot 示例。
- 外部公开资料未找到 ieeA 配置文档，需以代码为准。
- `docs/configuration.md` 内容与当前代码配置字段不一致（疑似旧版 ieeT 文档）。
- 已将 `docs/configuration.md` 更新为当前 ieeA 配置字段与 CLI 覆盖方式。

## Technical Decisions
| Decision | Rationale |
|----------|-----------|
| 使用 README 新增配置模板段落 | 与用户要求一致 |

## Issues Encountered
| Issue | Resolution |
|-------|------------|
| session-catchup 使用环境变量失败 | 改用 /Users/zhengcaiyi/.config/... 绝对路径 |

## Resources
- /Users/zhengcaiyi/.config/opencode/skills/planning-with-files/templates/task_plan.md
- /Users/zhengcaiyi/.config/opencode/skills/planning-with-files/templates/findings.md
- /Users/zhengcaiyi/.config/opencode/skills/planning-with-files/templates/progress.md
- /Users/zhengcaiyi/Desktop/博0/杂项/写点小玩意/iee翻译/ieeA/README.md
- /Users/zhengcaiyi/Desktop/博0/杂项/写点小玩意/iee翻译/ieeA/src/ieeA/rules/config.py
- /Users/zhengcaiyi/Desktop/博0/杂项/写点小玩意/iee翻译/ieeA/src/ieeA/defaults/config.yaml
- /Users/zhengcaiyi/Desktop/博0/杂项/写点小玩意/iee翻译/ieeA/docs/configuration.md

## Visual/Browser Findings
- 无
## 2026-02-04
- task_plan.md indicates a prior task completed: config template in README.
- README includes compilation config (engine: xelatex, timeout, clean_aux).
