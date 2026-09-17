# skill-auditor 模块契约 v1（并发开发的共同真源）

> 所有开发子代理以本文件为准。字段名、单位、路径不得自行变更；要改先在群里（主会话）提出。
> 设计方案与调研底稿存内部研发仓库（不随本包发布），结论均已内化到本文件与 references/。

## 总原则（每个模块都必须遵守）

1. **只读审计对象**：对被审计的 skill 目录/会话记录 100% 只读。任何写操作只允许写到输出目录（`--out`，默认 `./skill-audit-output/`）。
2. **失败降级不崩**：某 agent 适配器读不了/某文件解析失败 → 记入 `warnings`，跳过该项继续跑；退出码仍 0（除非致命：输出目录写不进）。
3. **零第三方网络依赖**：脚本层不联网（tiktoken 本地库除外）。token 计量用 `tiktoken o200k_base`。
4. **Python 3.9+，无 framework**，只用标准库 + tiktoken。每个脚本 `python3 scripts/<name>.py [--flags]` 直接跑，`--help` 有说明，`--json` 输出机器可读结果。
5. **数字诚实**：所有 token 数标注口径（`"tokenizer": "o200k_local"`）；使用统计标注窗口。

## 数据流与文件契约

```
collect.py ──→ 00-inventory.json ──→ measure.py ──→ 01-metrics.json ──→ SKILL.md 主循环(Agent)
     │                                                        │
     └──→ usage 统计(并入 inventory)                evaluate.py ──→ 02-eval-results.json
                                                              └→ 03-report.md (Agent 缝合,参考 references/report-format.md)
```

### 00-inventory.json（collect.py + usage.py 的输出）

```json
{
  "generated_at": "2026-09-17T03:00:00+08:00",
  "scan_seconds": 12.3,
  "agents": [
    {
      "agent": "claude-code",
      "detected": true,
      "capabilities": {"scan": true, "usage_stats": true},
      "skill_roots": ["/Users/x/.claude/skills", "/Users/x/.claude/plugins/cache/*/skills"],
      "notes": "listing budget 机制见 references/audit-rubric.md"
    },
    { "agent": "codex", "detected": true, "capabilities": {"scan": true, "usage_stats": true}, "skill_roots": ["..."], "notes": "" },
    { "agent": "hermes", "detected": false, "capabilities": {"scan": false, "usage_stats": false}, "skill_roots": [], "notes": "未安装" }
  ],
  "skills": [
    {
      "id": "claude-code::blue-video-script",
      "agent": "claude-code",
      "name": "blue-video-script",
      "path": "/abs/path/to/skill-dir",
      "symlink_target": "/abs/real/path 或 null",
      "scope": "user | plugin | project",
      "description": "frontmatter 的 description 原文（折叠块标量归一成单字符串）",
      "has_skill_md": true,
      "body_chars": 3338,
      "body_lines": 118,
      "ref_files": ["references/xx.md"],
      "ref_total_chars": 12345,
      "scripts_files": ["scripts/run.py"],
      "frontmatter_keys": ["name", "description", "allowed-tools"]
    }
  ],
  "usage": {
    "window_days": 30,
    "window_note": "Claude Code transcripts 默认保留 30 天，统计仅覆盖此窗口；终身计数来自 ~/.claude.json skillUsage（官方静态文件）",
    "sessions_scanned": 87,
    "records": [
      { "skill_id": "claude-code::blue-video-script", "activations": 12, "last_seen": "2026-09-16", "first_seen": "2026-08-20", "lifetime_count": 47 }
    ],
    "coverage": { "transcripts_found": true, "skip_env_detected": false }
  },
  "warnings": ["hermes: 未安装，跳过", "xxx: frontmatter 解析失败（块标量缩进异常），该 skill 仅计文件层"]
}
```

### 01-metrics.json（measure.py 的输出，逐 skill 加指标）

在 inventory 每个 skill 条目上追加：

```json
{
  "tokens": {
    "always": 220,          // description 的 o200k token 数（每次会话常驻）
    "on_trigger": 2222,     // SKILL.md body 的 o200k token 数（触发才加载）
    "refs_total": 9876,     // references 总量（按需加载，参考值）
    "tokenizer": "o200k_local",
    "accuracy_note": "本地计量，与 Claude 官方 tokenizer 偏差 ≤10%（本地实测）"
  },
  "structure_flags": ["oversized_description", "heavy_body_no_refs", "skeleton"],  // 判据见 audit-rubric.md
  "duplication": [ { "with": "claude-code::yyy", "jaccard": 0.42, "note": "换名疑似重复" } ],
  "usage_stats": { "activations": 12, "last_seen_days_ago": 1, "daily_avg": 0.4 },
  "priority": { "score": 87, "reasons": ["重", "少用"] }   // 优先级排序：最重×最少用优先，公式见 rubric
}
```

### 02-eval-results.json（evaluate.py 的输出）

```json
{
  "evaluated_at": "...", "model": "claude-sonnet-5(运行时实际)", "budget_usd": 2.0, "cost_note": "CLI 报告的 list-price 估算",
  "results": [
    {
      "skill_id": "claude-code::brainstorming",
      "prescreen": { "verdict": "uncertain | likely_native | likely_valuable | skipped | agent-upstream", "reason": "..." },
```

`agent-upstream`：脚本不判预筛时占位，Agent 在报告缝合前回填真值（三出口判据见 audit-rubric.md）。

```json
      "cases": [ { "name": "explore-needs", "with_score": 1.0, "without_score": 1.0 } ],
      "delta": 0.0,
      "verdict": "suspected_native_coverage | valuable | inconclusive",
      "evidence": "with=1.0 without=1.0 Δ=0.0；case 见 /path/to/results"
    }
  ]
}
```

## 各适配器事实（调研结论，collect.py 的适配器按此实现）

- **claude-code**：skill 根 `~/.claude/skills/`（注意 symlink，跟到实体算 body，别重复计）+ `~/.claude/plugins/cache/*/skills*/`（plugin scope）+ `~/.claude/agents/skills/`（A 实测发现的第 4 根，实际加载）+ `$CWD/.claude/skills`（project，与 user 同实体去重）。使用统计双源：①`~/.claude.json` 的 `skillUsage`（name → `{usageCount, lastUsedAt}`，**终身计数，静态文件零成本，优先采**；注意查找要全名回退裸名；pluginUsage 的 lastUsedAt 有种子化陷阱不可信，只有 usageCount 可用）②transcripts 窗口扫描（`~/.claude/projects/<proj>/<session>.jsonl` 里 `"name":"Skill","input":{"skill":"<name>"` + slash 调用的 `command-name` 块），窗口默认 30 天——lifetime_count 用源①，activations/last_seen 用源②。
- **codex**：skill 根 `~/.codex/skills`（含 `.system` 子根，scope 记 user 并在 notes 说明）+ `~/.agents/skills`（共享）+ plugins/cache 根（同类工具恰好漏这）+ `$CWD/.agents/skills`（project）。SKILL.md 同构。使用统计：rollout jsonl（`~/.codex/sessions/`）只计 function_call/custom_tool_call（listing 快照≠使用）。
- **hermes**：`~/.hermes/skills/<类别>/<skill>/SKILL.md`；会话 SQLite `~/.hermes/state.db`（本机未装，适配器写好但 detected=false 优雅跳过）。
- **未装检测**：根目录不存在 → `detected: false`，不告警不崩。

## 实现补充约定（2026-09-17 B 交付后固化，与上节同等效力）

- measure.py 按 `skill.path` 回读 SKILL.md/refs 计量（inventory 不嵌正文，审计同机执行路径有效）
- 01-metrics.json 附加顶层：`measured_at`、`metrics_meta`（always 合计 / usage 维度状态 / listing 预算提示），报告层引用
- usage 整体缺失时逐 skill `usage_stats: null`；"无记录=未用"结论以 `usage.sessions_scanned > 0` 为前提，否则报告标"数据不足"
- priority 公式（measure.py 实现）：`always_tokens 归一 ×0.5 + 少用程度 ×0.3 + body 重度 ×0.2`（少用程度 = 频率与久未用两维取最大；无 usage 数据按已知维度归一）

## 判定阈值（代码化，audit-rubric.md 是解释真身，代码里直接用这些数）

- description > 1024 字符 → `oversized_description`
- body > 8000 token 且 ref_files 为空 → `heavy_body_no_refs`
- body < 50 行且无 refs/scripts → `skeleton`
- Jaccard ≥ 0.55（对 **name+description+body** 混合分词：英文 \w+、中文 2-gram；加 name 会系统性抬高同名对相似度，是有意设计——跨 agent 同名同份副本靠它抓）→ 重复候选（人工确认级，不下死结论）
- eval 判定阈值（evaluate.py 常量）：**DELTA_FLAT = 0.1**（|Δ|≤0.1 且两份答卷高分为 suspected_native_coverage；Δ>0.1 为 valuable）/ **LOW_SCORE = 0.5**（两份答卷均 <0.5 为 inconclusive 回炉）
- listing 预算提醒（仅 claude-code）：全部 always 之和 > **2000 token**（= 200k 上下文 × 1% ≈ 官方 8000 字符预算（官方口径）。Codex 机制 min(2% context, 8000 字符)量级相同）时报告层警示——报告层给提示不做硬判

## 报告/不动手红线

- 所有脚本**不得**删/改/移动任何被扫描文件。处置建议只在报告文本层，且带"建议人工确认"标注。
