# bulus-skill-auditor 公共数据契约

本文定义 v0.2.0 的三个机器可读产物及其解释边界。实现可以增加同一 major 内的可选字段，但不得改变既有字段的含义。

## 1. 版本与兼容

`00-inventory.json`、`01-metrics.json`、`02-eval-results.json` 顶层都必须包含：

```json
{
  "schema_version": "2.0",
  "schema_name": "bulus-skill-auditor.inventory | bulus-skill-auditor.metrics | bulus-skill-auditor.eval"
}
```

- 消费者遇到未知 major 时必须明确报“不支持”，不能猜测字段。
- v1 输入可以在读取边界补齐缺失字段，但补出的活跃状态只能是 `unknown`，发现置信度只能是 `inferred`。
- `generated_at`、`evaluated_at`、`scan_seconds`、`duration_seconds`、本次费用等运行元数据允许变化；业务身份、排序和聚合在同一输入下必须稳定。

## 2. 全局安全边界

- 发现、计量、使用统计、评测和报告不得修改被审计目录、会话记录、Agent 配置或插件缓存。
- 只允许写用户指定的 `--out-dir`、`--out` 及其临时副本。
- 管理命令只读；审计器不直接发起外部 HTTP 请求。管理命令自身可能按所属产品的行为刷新市场状态。
- 配置降级只读取插件与市场相关的白名单字段。provider、凭证、完整环境变量、整段配置或未经筛选的命令输出不得进入 JSON、warning 或报告。
- 绝对路径只保留在本地原始产物。分享副本必须经过路径脱敏，且不得原地覆盖原件。

## 3. `00-inventory.json`

### 3.1 顶层

```json
{
  "schema_version": "2.0",
  "schema_name": "bulus-skill-auditor.inventory",
  "generated_at": "ISO-8601",
  "scan_seconds": 0.0,
  "agents": [],
  "skills": [],
  "usage": {},
  "issues": [],
  "warnings": []
}
```

`skills[]` 为兼容名称，v2 表示“运行时可见或保守推断的可审计组件”，组件可以是 skill、command 或 agent。

### 3.2 组件身份

每个 `skills[]` 项必须包含：

```json
{
  "instance_id": "claude-code::i::<20 hex>",
  "id": "claude-code::runtime-name",
  "logical_id": "claude-code::runtime-name",
  "conflict_group": null,
  "agent": "claude-code",
  "component_type": "skill",
  "name": "runtime-name",
  "runtime_name": "runtime-name",
  "component_name": "runtime-name",
  "declared_name": null,
  "directory_name": "directory-name",
  "namespace": null
}
```

- 主键是 `instance_id`。跨模块关联不得使用可能重复的 `id`。
- `id` 与 `logical_id` 为兼容逻辑名，值都是 `agent + "::" + runtime_name`，允许重复。
- 同一 Agent、同一 `runtime_name` 有多个实例时，所有实例的 `conflict_group` 都等于 `logical_id`；否则为 `null`。
- `name` 是兼容别名，必须等于 `runtime_name`。
- `declared_name` 是 frontmatter 原始声明，可为空；它不自动等于运行时名称。

`instance_id` 的稳定生成规则：

```text
agent + "::i::" +
sha256(
  NUL-join(
    agent,
    component_type,
    runtime_name,
    install_scope,
    normalized lexical source_file,
    source_realpath
  )
)[:20]
```

lexical path 与 realpath 都进入摘要，确保同一实体以不同路径被运行时明确暴露时不会被意外折叠。Claude 适配器若按 Claude 的规则先做 realpath 合并，应在生成实例前完成。

### 3.3 名称语义

- Claude 独立 skill 默认使用 Claude 的目录/运行时语义，不把 frontmatter `name` 当作默认运行时名称。
- Codex 独立 skill 使用合法的 frontmatter `name`。
- 插件组件使用 `plugin_name + ":" + component_name`，不把 marketplace 拼入运行时名。
- `plugin_id`、`runtime_name`、`component_name` 不得互相替代。
- 大小写保持原样。重复运行时名称全部保留；没有可靠 precedence 证据时不输出 winner。

### 3.4 来源字段

每个组件必须包含：

```json
{
  "scope": "user",
  "install_scope": "user",
  "source_kind": "standalone",
  "path": "<local path>",
  "realpath": "<local path>",
  "source_file": "<local path>/SKILL.md",
  "source_realpath": "<local path>/SKILL.md",
  "symlink_target": null,
  "plugin_id": null,
  "plugin_name": null,
  "marketplace": null,
  "plugin_version": null,
  "manifest_declared": null
}
```

枚举：

- `scope`、`install_scope`：`user | project | local | plugin | system | shared | builtin | unknown`
- `source_kind`：`standalone | plugin | builtin`

插件的 `plugin_id` 保存完整安装 ID，例如 `plugin@marketplace`；模型可见命名空间另存于 `namespace`。

### 3.5 活跃性与账单资格

```json
{
  "active_state": "active",
  "discovery_confidence": "runtime_probe",
  "discovery_method": "runtime-probe-name",
  "auditable": true,
  "source_format": "skill-md",
  "accounting": {
    "listing": "confirmed",
    "trigger": "confirmed",
    "reason": "runtime evidence"
  }
}
```

枚举：

- `active_state`：`active | unknown`
- `discovery_confidence`：`runtime_probe | management_cli | known_root | inferred`
- `accounting.listing`、`accounting.trigger`：`confirmed | estimated | excluded`

规则：

- 只有 `active_state=active` 的组件可以进入 confirmed 账单。
- `unknown` 可以测量，但必须进入 inferred 账单。
- 禁用、inactive、旧版本和 cache-only 项不得进入 `skills[]`；只记录到 `agents[].discovery.excluded_counts` 或结构化 issue。
- SKILL.md 和运行时证据明确暴露的 command 可以审计。
- 没有可靠加载语义的 plugin agent 可以列入 inventory，但其账单必须为 `excluded`。

### 3.6 内容兼容字段

继续保留：

```text
description
has_skill_md
body_chars
body_lines
ref_files
ref_total_chars
scripts_files
frontmatter_keys
```

`ref_files` 与 `scripts_files` 使用相对组件根的稳定路径。读取失败必须形成结构化 issue，不能把未知值伪装成已确认的零。

### 3.7 Agent 发现覆盖

每个 `agents[]` 项包含：

```json
{
  "agent": "claude-code",
  "detected": true,
  "capabilities": {
    "active_probe": true,
    "plugin_listing": true,
    "usage_stats": true,
    "component_types": ["skill", "command", "agent"]
  },
  "skill_roots": [],
  "notes": "",
  "discovery": {
    "status": "complete",
    "methods": [],
    "cli_version": null,
    "fallback_reason": null,
    "excluded_counts": {},
    "component_coverage": {}
  }
}
```

- `discovery.status`：`complete | partial | fallback | unavailable`
- `skill_roots` 只列本次真正采用的 active/unknown 根，不列通配 cache。
- 只有 `complete` 才能在报告中称“当前全量”；其他状态必须写“已确认清单 + 推断候选”。

### 3.8 结构化问题

`issues[]` 是机器判断的诊断源：

```json
{
  "code": "stable-code",
  "severity": "warning",
  "agent": "claude-code",
  "stage": "discovery",
  "message": "safe human-readable message",
  "path": null,
  "safe_context": {}
}
```

枚举：

- `severity`：`info | warning | error`
- `stage`：`discovery | parse | usage | eval | report`

`warnings[]` 只是 `issues[]` 中 warning/error 的确定性文本投影，不是机器判断源。issue 不得包含密钥、完整环境、provider 配置或未经白名单筛选的命令输出。

## 4. 发现语义

### 4.1 Claude Code

- 每次采集最多运行一次带短超时的 `claude plugin list --json`。
- 只接纳 `enabled=true` 的当前 `installPath`、`version`、`scope`。
- `.claude-plugin/marketplace.json` 按 `plugin_id` 的 plugin 名选择唯一 `plugins[]` 项，只展开显式组件。
- `.claude-plugin/plugin.json` 优先使用显式 `skills/commands/agents`；只有缺少 `skills` 声明时才采用默认 `skills/`。
- 默认独立 skill 根只有用户目录和当前项目的 `.claude/skills`。额外根必须由本次运行时证据明确列出。
- 管理命令超时、非零退出或 JSON 无效时形成 issue 并保守降级，不递归整个插件 cache，也不把目录存在等同于启用。

### 4.2 Codex

- 优先解析只读的 prompt-input probe：roots 表与 Available skills 的 `(file: rN/...)` 引用。
- 每条引用必须安全映射到对应 root 内；递归嵌套、`.system`、项目根和插件根都可由 probe 明确暴露。
- prompt 中重复名称或重复路径实例全部保留，不采用“首个获胜”。
- root 编号缺失、格式漂移、区块缺失或越界引用会触发保守 fallback。
- fallback 时，插件只来自 `codex plugin list --json` 中 `installed=true && enabled=true` 的选定版本。
- fallback 扫描到的独立组件只能标为 `active_state=unknown`、`discovery_confidence=inferred`。
- 仅 TOML enabled、仅 cache 存在、缺少合法名称或未在可靠 probe 中出现的项不得冒充 confirmed active。

### 4.3 Hermes

Hermes 适配器保持实验性、只读和失败降级。没有权威运行时 probe 时，文件系统发现默认标为 `active_state=unknown`、`discovery_confidence=inferred`，不得与 confirmed active 混称完整清单。

## 5. `01-metrics.json`

### 5.1 顶层

```json
{
  "schema_version": "2.0",
  "schema_name": "bulus-skill-auditor.metrics",
  "measured_at": "ISO-8601",
  "skills": [],
  "usage": {},
  "metrics_meta": {},
  "issues": [],
  "warnings": []
}
```

measure 只消费 inventory 的组件和状态，从 `source_file` 读取内容，不重新发现组件，也不改变 `active_state`。

### 5.2 每组件指标

在 inventory 组件上追加：

```json
{
  "tokens": {
    "always": 0,
    "on_trigger": 0,
    "refs_total": 0,
    "tokenizer": "o200k_local",
    "accuracy_note": "engineering estimate",
    "accounting_status": "confirmed"
  },
  "structure_flags": [],
  "duplication": [
    {
      "with": "canonical instance_id",
      "with_logical_id": "agent::runtime-name",
      "jaccard": 0.0,
      "note": "candidate only"
    }
  ],
  "usage_stats": null,
  "priority": null
}
```

- `tokens.accounting_status`：`confirmed | inferred | excluded`
- duplication 的 `with` 必须是 canonical `instance_id`。
- 相同 physical content 跨 Agent 仍按各 Agent 账单保留。
- 重复度只产生候选，不自动合并、删除或决定 precedence。
- priority 只对 `auditable=true` 且 accounting 非 excluded 的组件排序。
- 使用状态未知时不得当作零使用。

### 5.3 汇总

`metrics_meta.always_total_tokens` 只表示 active 且 listing confirmed 的常驻总量。另包含：

```json
{
  "always_inferred_total_tokens": 0,
  "by_agent": {
    "claude-code": {
      "confirmed_components": 0,
      "inferred_components": 0,
      "excluded_components": 0,
      "confirmed_always_tokens": 0,
      "inferred_always_tokens": 0
    }
  }
}
```

confirmed、inferred、excluded 不能相加后包装成一个“当前总量”。

## 6. 使用统计

### 6.1 顶层与覆盖

```json
{
  "window_days": 30,
  "window_note": "",
  "sessions_scanned": 0,
  "records": [],
  "coverage": {
    "status": "complete",
    "transcripts_found": true,
    "skip_env_detected": false,
    "by_agent": {}
  }
}
```

每个 `coverage.by_agent[agent]` 包含：

```text
status
sessions_scanned
transcripts_found
history_disabled
files_unreadable
parse_errors
undated_events
direct_events
matched_activations
unmatched_activations
ambiguous_activations
limitations[]
```

`status` 使用 `complete | partial | unavailable`。records 为空时也必须说明是“确实扫到零”还是“数据不可用”。

### 6.2 使用记录

```json
{
  "record_id": "stable id",
  "agent": "claude-code",
  "skill_instance_id": null,
  "skill_id": "logical or synthetic id",
  "matched": false,
  "match_status": "unmatched",
  "candidate_instance_ids": [],
  "source_ref": null,
  "source_ref_hash": "stable hash",
  "name_hint": null,
  "source_counts": {},
  "activations": 1,
  "first_seen": "ISO-8601 or null",
  "last_seen": "ISO-8601 or null",
  "lifetime_count": null
}
```

- `match_status`：`matched | unmatched | ambiguous`
- matched 的唯一关联键是 `skill_instance_id`。
- unmatched/ambiguous 的 `record_id` 与兼容 `skill_id` 使用稳定 synthetic ID：

```text
agent + "::unmatched::" +
sha256(agent + NUL + source_kind + NUL + normalized_ref)[:20]
```

- 多候选必须记录为 `ambiguous`，不能任意归到某一实例。
- 未知真实调用聚合次数并保留首末时间；未知 slash 内置命令忽略。
- 无时间戳事件只增加 `coverage.undated_events`，窗口外事件完全忽略。

### 6.3 Claude Code 使用事实

只接受：

1. 顶层 `type=assistant`；
2. `message.role=assistant`；
3. 直接 `message.content[]` 中 `type=tool_use,name=Skill`。

slash 只接受普通顶层 user 的直接字符串 content 中 `<command-name>/…</command-name>`。compact summary、attachment/meta、prompt snapshot、skill listing、dynamic skill、invoked skills、attributionSkill 等不计入，也不生成 unmatched。

名称解析顺序：完整 `runtime_name` 唯一匹配 → 唯一尾名兼容 → ambiguous → unmatched。

### 6.4 Codex 使用事实

只接受顶层 `type=response_item` 且直接 payload 是：

- `function_call`，`name in {exec_command, shell}`；或
- `custom_tool_call`，`name=exec`。

只在解码后的直接 `arguments/input` 中匹配 inventory 的 `source_file`、`source_realpath` 和 symlink alias。未知时才抽取绝对 `SKILL.md` 路径为 unmatched。

world_state、session_meta、compacted history、call output、event message、普通 message、reasoning、apply_patch 等不计入。一个顶层 shell call 对同一实例最多计一次，对不同实例可各计一次。报告称其为“技能文件加载/引用次数”，不称为用户意图级调用。

## 7. `02-eval-results.json`

### 7.1 顶层

```json
{
  "schema_version": "2.0",
  "schema_name": "bulus-skill-auditor.eval",
  "evaluated_at": "ISO-8601",
  "runtime_agent": "claude-code",
  "backend": "claude-plugin-eval",
  "status": "complete",
  "requested_model": "execution-model",
  "requested_judge_model": null,
  "model": "effective-model | mixed | unknown",
  "judge_model": null,
  "budget_usd": 0.0,
  "total_budget_usd": 0.0,
  "total_cost_usd": 0.0,
  "cost_scope": "this_run_only",
  "cost_note": "",
  "concurrency": 1,
  "runs": 1,
  "dry_run": false,
  "results": [],
  "errors": [],
  "warnings": []
}
```

枚举：

- `runtime_agent`：`claude-code | other | unknown`
- `backend`：`claude-plugin-eval | none`
- `status`：`complete | partial | unsupported_runtime | error | dry_run`

`model` 只能从各结果的 raw effective model 汇总为单一值、`mixed` 或 `unknown`，不能从命令行标签直接填写。

### 7.2 每组件评测结果

```json
{
  "skill_instance_id": "canonical instance_id",
  "skill_id": "compatible logical id",
  "status": "complete",
  "prescreen": {},
  "requested_model": "execution-model",
  "model": "effective-model",
  "judge_model": null,
  "claude_version": "",
  "source_schema_version": "",
  "fingerprint": "",
  "cache_hit": false,
  "cacheable": true,
  "raw_result_path": null,
  "cases": [],
  "delta": null,
  "verdict": "inconclusive",
  "evidence": "",
  "cost_usd": 0.0,
  "cost_usd_this_run": 0.0,
  "duration_seconds": 0.0,
  "partial": false,
  "partial_reason": null,
  "error": null
}
```

- `status`：`complete | cached | partial | unsupported_runtime | error | dry_run`
- `verdict`：`suspected_native_coverage | valuable | inconclusive | content_value_unverified`
- 只允许评测 `auditable=true` 且能唯一解析到 `skill_instance_id` 的组件。
- `--skills` 可兼容接受旧 logical id，但多候选必须在启动付费进程前报歧义。

### 7.3 每案例结果

```json
{
  "name": "case-name",
  "effective_model": "model | null",
  "status": "complete",
  "with_score": null,
  "without_score": null,
  "delta": null,
  "with_runs": [],
  "without_runs": [],
  "skipped_paid_graders": false,
  "errors": []
}
```

- `status`：`complete | incomplete | error`
- effective model 优先使用非空 `suite.modelOverride` 覆盖全部 case，否则使用 `cases[].model`。
- case 模型全同才形成 result.model；不同为 `mixed`，全空为 `unknown`。
- 分数原则上只读取官方 `cases[].aggregates.score`、`scoreWithout`、`delta`，不从不完整 run 的均值重建正式分差。

### 7.4 可判定门槛

以下任一情况出现时，结果不得给出 valuable/native 结论，只能是 `inconclusive`：

- 顶层 partial；
- 任一 run error；
- 任一 `skippedPaidGraders=true`；
- 任一 case 缺少可比较的两臂；
- 缺 case 或缺臂；
- raw schema major 未知；
- effective model 与明确 requested model 不一致。

unsupported runtime 的 verdict 为 `content_value_unverified`。已经完成的 case 分数可以作为局部证据保留，但不能代表整个组件。

### 7.5 运行时路由

- `--runtime-agent auto|claude-code|other` 的显式值优先。
- `auto` 只在可靠的 `CLAUDECODE=1` 信号存在时选择 Claude backend。
- `other/unknown` 即使 PATH 中存在 `claude` 也不调用外部评测，输出 `$0`、`unsupported_runtime`、`content_value_unverified`。
- 非 dry-run 的 Claude 路由必须在任何付费进程启动前取得 concrete `--model`。
- 实际命令必须独立传递 `--model <execution-model>`、可选 `--judge-model <judge-model>` 与固定 `--concurrency 1`。
- execution model 不自动复制给 judge。

### 7.6 预算与退出

- exit 0/1 且 JSON 完整合法时可以解析。
- exit 2 若存在合法 partial JSON，先计入 raw 中的真实 `costUsd`，将结果标为 partial/inconclusive，再停止后续付费项。
- 付费进程一旦启动但无法取得可信成本，必须 fail closed 并停止。
- `total_cost_usd` 只记本次新花费；cache hit 的本次费用为零。
- `total_budget_usd` 是后续任务的启动上限。固定 `concurrency=1` 仍可能被一个在途 run 小幅突破，报告必须披露这一点。

### 7.7 缓存

fingerprint 至少覆盖：

```text
skill_instance_id
skill 副本全部纳入文件的内容摘要
case / prompt / graders 摘要
runs
execution model
judge model（未指定时使用 cli-default-unpinned）
ablation mode
Claude Code 版本
受支持的 eval schema 版本
```

- `model=unknown` 或 `mixed` 的结果不可缓存。
- raw 证据按 instance、模型和 fingerprint 隔离。
- 启动失败不得读取旧 raw。
- 当前 `02-eval-results.json` 只包含本次请求及其精确 cache hit，不混入未请求的历史结果。

## 8. 报告语义

- 所有数量、费用和 token 聚合都使用 canonical `instance_id` 与结构化状态。
- 按 Agent 分列 confirmed active、inferred/unknown、excluded component 的数量和 token。
- unmatched 与 ambiguous 从 `match_status` 统计，不从字段缺失猜测。
- 评测表逐行展示实际 model、status、partial/cache、本次费用和 verdict。
- 顶部预算读取 `total_budget_usd`，花费读取 `total_cost_usd`；不得从历史 results 重新求和冒充本次费用。
- 只有完整且可判分的 complete/cached 结果计入“已验证”。partial、unsupported、error 单列为“内容价值未验证”或“无结论”。
- 报告不得重新计算官方 delta。
- 所有处置是建议，必须人工确认；审计器不修改被审计对象。

## 9. 确定性与排序

- JSON 使用 UTF-8、`ensure_ascii=False`、`indent=2`。
- roots、skills、issues、usage records、eval results 使用稳定书面排序键。
- 同一输入重复采集时，除明确的运行元数据外，`instance_id`、数组顺序、issue 顺序与聚合值必须一致。
- 多实例不得因为逻辑 ID 重复而被覆盖。

## 10. 分享副本

`redact_report.py` 接受单个文件或整个输出目录：

```bash
python3 scripts/redact_report.py ./skill-audit-output --out ./skill-audit-output-share
```

分享副本必须：

- 不修改输入文件或目录；
- 处理 JSON 字段与 Markdown/JSONL/文本中的嵌入路径；
- 覆盖 macOS `/Users/...`、Linux `/home/...` 与 `/root/...`、Windows `C:\Users\...` 和 `C:/Users/...`；
- 覆盖 `path`、`realpath`、`source_file`、`source_realpath`、`symlink_target`、`skill_roots`、插件 `installPath`、`source_ref`、`raw_result_path` 等字段；
- 保留 URL、slash 命令与相对引用；
- 目录输出位于输入之外，遇到无法安全处理的二进制文件或符号链接时停止。
