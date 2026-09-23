# 报告格式（两段式产出：骨架脚本渲染 + 判断注入）

> 何时读：缝合最终报告时。原则：**骨架字段（表格/数字/聚合）由脚本渲染，重跑等价；判断内容（诊断叙述/建议）走注入位，随 json 留档**——两层不混写。
> v2 起，骨架的一切聚合都按 Agent 分账、以 canonical `instance_id` 为唯一主键；本文件结构与 `render_report.py` 的实际输出一一对应。

## 产物清单（一次审计最多产出四个文件）

| 文件 | 内容 | 生成方式 |
|---|---|---|
| `03-report.md` | 主报告（下述结构） | 骨架脚本渲染 + Agent 注入诊断段 |
| `Skill清单.md` | 清单模式产物：按 Agent 分组的实例清单 + 场景建议（轻量入口，日常翻） | 骨架渲染 + Agent 注入场景建议 |
| `01-metrics.json` / `02-eval-results.json` | 机器可复核数据（每条结论的数字都能指回这里） | 脚本 |

## 03-report.md 结构（与 render_report.py 输出逐节对应）

```markdown
# Skill 审计报告 · <日期>（取 00 的 generated_at，保证可复现）

> 口径声明（脚本固定渲染，Agent 不得改写）：
> - 覆盖结论：只有 discovery=complete 的 Agent 才写「当前全量」；否则写「已确认清单 + 推断候选」
> - 按 Agent 分账：不同 Agent 的 listing demand 绝不相加成一张"每次会话账单"
> - token 为 o200k_local 近似；always 只计 description，不含运行时可能附加的 name/格式开销
> - active+listing confirmed 才进 confirmed 账单；unknown/estimated 与 excluded 分列
> - 未知 usage 保持未知，不按 0 激活处理；跨 Agent 副本只表示维护关系
> - 深度评测（若跑）：总预算（启动上限）＋本次实际新增花费＋实际模型汇总

## 一、总览（按 Agent 分账）
| Agent | discovery | confirmed active | confirmed token | inferred/unknown | inferred token |
|       | excluded | excluded token | listing demand | injected upper bound | potential overflow |
<!-- 每行预算口径以 HTML 注释附带：budget basis / 含 inferred 的潜在需求 / 含 inferred 的潜在溢出 -->

## 二、真账单（canonical instance 全量明细）
| instance | runtime | agent | type | active | listing/trigger | 常驻token | 触发token | refs | usage | priority | 标记 |

## 三、诊断事实（不替用户执行处置）
### 使用覆盖（按 Agent：status/sessions/unreadable/parse errors/undated/matched activations/limitations）
### 重复候选（跨 Agent 维护副本 N 对 / 同 Agent 重复候选 N 对，均人工确认级）
### 结构问题（structure_flags 计数 + 健康候选数量）
<!-- INJECT: Agent 按 audit-rubric 补充诊断判断 -->

## 四、高嫌疑名单（每个 Agent 独立归一，跨 Agent 分数不可直接比较）
| # | instance | runtime | score | Agent 内归一理由 |

## 五、处置建议（注入位）
<!-- INJECT: 按 refactor-playbook 写信号、预计收益、风险前提和人工确认框 -->

## 六、深度评测结果（只消费官方聚合与显式状态）
<!-- 模型行：实际模型汇总 / 请求执行模型 / judge / runtime+backend / 顶层状态
     预算行：总预算（启动上限）+ 本次实际新增花费 + cost_scope
     固定披露：concurrency=1 时一个在途 run 仍可能小幅突破预算
     分桶行：已验证 N / 内容价值未验证 N / 各 status 计数
     表行：instance | runtime | 实际模型 | 请求模型 | judge | status | partial/cache | cases | 官方Δ | 判定 | 本次成本 -->

## 七、附录：issues 与复核入口
<!-- structured issues 计数 + 复核命令表（jq 单行，按 Agent 分组口径） -->
```

## 硬性口径（骨架层的机械规则，注入内容也不得违反）

- **绝不合并 Agent 账单**：任何"常驻总账 = 全部 skill 的 Σalways"式全局求和都是 v1 遗留口径，禁止出现。跨 Agent 的机器字段只存在于 `metrics_meta`（`total_note` 已注明仅供对账），报告正文只按 Agent 分行列。
- **三种数量分开**：listing demand（confirmed 需求）、injected upper bound（已知预算下最多注入）、potential overflow（confirmed 超出预算的部分）是三个不同概念，不得混写；没有同单位上限的 Agent 写"无可比 token 上限"，不猜。
- **主键是 instance_id**：同 Agent 同 runtime_name 的多个实例都保留、各自成行；旧 `id`（logical id）只作兼容展示。处置建议引用组件时用 instance_id。
- **活跃性三态分列**：confirmed active / inferred(unknown) / excluded 各有独立列；只有 discovery=complete 才能声称"当前全量"。
- **usage 未知 ≠ 0**：usage_stats 为 null 的组件显示"未知"；只有 coverage=complete 的 Agent 里才允许出现"已确认窗口零激活"。
- **评测只认显式状态**：已验证 = status complete/cached + 全 case 可判分 + 实际模型已知；partial / unsupported / error / 模型 unknown 或 mixed 一律单列"内容价值未验证"，Δ 只引用官方 aggregate，不重算；预算读 `total_budget_usd`、花费读 `total_cost_usd`（本次口径），不把逐条 result 成本求和冒充总花费。
- **legacy v1 输入**：报告顶端必须出现固定 banner「legacy inferred，非当前活跃性证明」，全篇按 inferred/unknown 呈现。

## 骨架/注入字段划分（硬约束）

- **骨架（脚本渲染，Agent 不得改）**：所有表格数字、聚合值、优先级分数、Δ 值、口径声明段、预算/成本行
- **注入位（Agent 写，经 `report-inject.json` 留档）**：三节的判断叙述（`diagnosis`）、四节的建议动作（`suspect_actions`）、五节全部（`recommendations`）、清单的场景建议（`inventory_list`）
- 注入文件解析失败时保留占位注释，不阻塞渲染
- 注入文本同样过表格安全转义（`|`/换行/反斜杠），不得用注入位突破上面的硬性口径

## 失配警示（机械化，完成≠合理原则）

脚本渲染时检查并**显性呈现**（不靠 Agent 注意力）：
- 扫描到 0 个 component → 不出报告，render 直接退出码 2（输入异常）
- usage 覆盖 per-Agent 标注 status（complete/partial/unavailable）；非 complete 的 Agent 里"零激活"结论不可信，limitations 逐 Agent 呈现
- listing 超限（potential overflow > 0）→ 总览行直接给出溢出 token 数（静默截断风险，用户感知不到但伤害最大）
- source_file 读取失败 / ref 路径越界 → 该组件 measurement_status=incomplete，数字显示"未确认"并落 structured issue，不默认为 0

## Skill清单.md 结构（轻量产物，v2 口径）

```markdown
# 我的 Skill 清单 · <日期>（<N> 个实例）
> 按 Agent 分组；active confirmed、inferred/unknown、excluded 不混写。

## <agent>（<n> 个实例）
- <runtime_name> — <instance_id> / <component_type> / <accounting_status> / <usage 口径>
<!-- INJECT: 仅补场景建议，不改脚本生成的实例与状态 -->
```
