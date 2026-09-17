# Changelog

## 0.1.0（2026-09-17）

首版。跨 agent skill 审计（claude-code / codex / hermes 插座式）。

- **静态层**：`collect.py`（多 agent 插头扫描 + frontmatter 健壮解析 + 使用统计双源：transcripts 窗口 / skillUsage 终身）→ `measure.py`（o200k token 计量、中英混合 Jaccard 重复检测、结构 flags、优先级排序、listing 预算警示）
- **深度层**：`evaluate.py`（对比考试编排：plugin pkg 组装 → 官方 eval CLI 双臂 → Δ 汇总 → 缓存）
- **判断层**：SKILL.md 薄路由 + references 四件（审计判据含官方口径对照 / 出题铁律含判定矩阵 v2 / 重构手册 R1-R6 / 报告格式骨架+注入位）
- 判定矩阵 v2：首轮实测发现"双臂都高分 + case 无区分度 = inconclusive 回炉"，出题铁律升级为"考私有资产不考通用能力"
- 官方口径对齐：unused 三档、listing 成本（name+description 一行、≤1536 字符、预算 context×1%）——官方公开机制结论
