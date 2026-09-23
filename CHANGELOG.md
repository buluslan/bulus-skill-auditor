# Changelog

## 0.2.0（2026-09-23）

- 引入 v2.0 公共数据契约：组件使用稳定 `instance_id` 关联，已确认、推断与排除项按 Agent 分列
- 收紧 Claude Code 与 Codex 的发现和使用统计口径，失败时结构化降级，不把 cache、快照或间接历史误报为当前使用
- 深度评测增加运行时路由、真实执行模型、可选 judge 模型、串行预算状态和内容绑定缓存；部分结果不再产出正式价值结论
- 报告按实际模型、状态和本次费用展示结果，并明确总预算是后续任务的启动上限
- 脱敏工具支持对整个输出目录生成不改原件的分享副本，覆盖 JSON、JSONL、Markdown 与文本中的 macOS、Linux、Windows 用户路径
- README 增加可复制安装步骤、脚本报告骨架说明、分钟级耗时口径与完整隐私边界
- CI 增加 Python 3.9 门禁并自动运行全部离线 fixture
- 发布前审查修复：脱敏覆盖裸 `/var`、`/etc`、`file:`/`scp` 前缀与深嵌套结构；Codex probe 重复条目改为去重告警而非中断采集；`--max-cost-usd`/`--total-budget-usd` 拒绝 NaN/Inf；measure/render/evaluate 对非对象 JSON 与混型 agent 字段干净报错不崩溃；`--skills` 解析为空直接拒绝；usage 覆盖有读不出文件时降级 partial 不虚标

## 0.1.2（2026-09-17）

- 恢复项目简介中的 buluslan / 新西楼.AI 研发者署名，并与发布门面保持一致

## 0.1.1（2026-09-17）

- 增加单次运行总预算参数与校验
- 增加报告路径脱敏工具、离线测试和 GitHub Actions
- 明确 token 成本是工程估算，并标注实验性适配器边界

## 0.1.0（2026-09-17）

- 首次发布跨 Agent skill 审计能力，支持本地发现、三笔 token 估算、使用统计、重复与结构诊断
- 提供预算受控的带 skill / 不带 skill 对比评测
- 提供可复核的 Markdown 报告骨架与改造优先建议
