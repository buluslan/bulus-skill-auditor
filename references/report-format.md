# 报告格式（两段式产出：骨架脚本渲染 + 判断注入）

> 何时读：缝合最终报告时。原则：**骨架字段（表格/数字/聚合）由脚本渲染，重跑等价；判断内容（诊断叙述/建议）走注入位，随 json 留档**——两层不混写。
> v2 起，骨架的一切聚合都按 Agent 分账、以 canonical `instance_id` 为唯一主键；本文件结构与 `render_report.py` 的实际输出一一对应。

## 读者预设与说话方式（注入层硬约束）

**读者是谁**：装了一堆 skill 的普通使用者。会装、会用、会说"帮我审计一下 skills"，但不懂 token 计量、instance_id、JSON、schema。报告是写给这个人看的，不是写给工程师同行看的。

**注入段的成文规矩**：

1. **术语必须翻译**：注入文本里出现任何术语，第一次出现时跟一个括注人话。对照表（骨架表头已内置同名速查，注入层保持同一套说法）：

   | 术语 | 对用户说成 |
   |---|---|
   | 常驻 / listing / always | 「常驻」= 每次会话都挂着的简介 |
   | 触发 / trigger / body | 「触发」= 被调用时才进对话的正文 |
   | refs / 参考文件 | 按需翻的资料库 |
   | token | AI 的字数计量（1 token 约半个到一个汉字） |
   | confirmed / inferred / excluded | 已确认 / 推断 / 排除（证据等级） |
   | instance_id | 实例 ID（同名的两个副本各有一个） |
   | listing 预算 / budget | 名片区容量 |
   | potential overflow | 装不下的部分（后面的简介可能根本没被看到） |
   | 静默截断 | 系统不提示、默默把超出的简介丢掉 |
   | discovery=complete | 扫描状态=完整 |

2. **数字必须跟后果**：不孤立报数字，每个关键数字后面跟一句"这意味着什么"。❌「potential overflow 6,885」→ ✅「有 6,885 token 的简介装不进名片区——这部分简介等于白写了，AI 根本看不到」。
3. **建议必须可执行**：处置建议写给不做工程的人：说清楚"动哪个（用名字，不是实例 ID）、怎么动（禁用/改瘦/删掉的点击路径或一句话操作）、动了会怎样"。
4. **自检**：注入段写完通读一遍——把读者想象成不懂任何英文缩写的人，任何一格需要先解释才能懂的表述，就地改写成速查表里的说法。

骨架表格的列头与枚举值已由脚本渲染成中文；注入文本不得把术语改回英文缩写风格。

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
> - 覆盖结论：只有扫描状态=完整的 Agent 才写「当前全量」；否则写「已确认清单 + 推断候选」
> - 按 Agent 分账：不同 Agent 的账目绝不加成一张「每次会话总账单」
> - 名词速查：「常驻」=每次会话都挂着的简介；「触发」=被调用时才进对话的正文；「参考文件」=按需加载的资料；token = AI 的字数计量（1 token 约半个到一个汉字）；confirmed（已确认）/inferred（推断）/excluded（排除）= 证据等级
> - token 为 o200k 近似；常驻只计简介文本，不含运行时可能附加的名字/格式开销
> - 只有运行时确认在用的组件才进「已确认」账单；推断/未知与排除项分开列
> - 使用次数未知就写未知，不当成 0；跨 Agent 的同款只算维护关系（改一处要记得另一处）
> - 深度评测（若跑）：总预算（启动上限）＋本次实际新增花费＋实际模型汇总

## 一、总览（按 Agent 分账）
| Agent | 扫描状态 | 确认在用 | 常驻token（确认） | 推断/未知 | 推断token | 已排除 | 排除token | 简介总需求 | 预算内可注入 | 超出预算 |
<!-- 每行预算口径以表下 bullet 附带：预算依据 / 含 inferred 的潜在需求 / 含 inferred 的潜在溢出 -->

## 二、真账单（全部组件明细）
| 实例ID | 名字 | Agent | 类型 | 状态 | 计量口径 | 常驻token | 触发token | 参考文件token | 30天使用 | 优先分 | 标记 |

## 三、诊断事实（不替用户执行处置）
### 使用覆盖（按 Agent：扫描状态/会话数/读不出的文件/解析错误/无日期事件/匹配到的调用/限制说明）
### 重复候选（跨 Agent 维护副本 N 对 / 同 Agent 重复候选 N 对，均人工确认级）
### 结构问题（structure_flags 计数 + 健康候选数量）
<!-- INJECT: Agent 按 audit-rubric 补充诊断判断（按「读者预设与说话方式」说人话） -->

## 四、高嫌疑名单（每个 Agent 独立归一，跨 Agent 分数不可直接比较）
| # | 实例ID | 名字 | 分数 | 排序理由（Agent内归一） |

## 五、处置建议（注入位）
<!-- INJECT: 按 refactor-playbook 写信号、预计收益、风险前提和人工确认框；动作写给非技术用户 -->

## 六、深度评测结果（只消费官方聚合与显式状态）
<!-- 模型行：实际模型汇总 / 请求执行模型 / 评分模型 / runtime+backend / 顶层状态
     预算行：总预算（启动上限）+ 本次实际新增花费 + cost_scope
     固定披露：concurrency=1 时一个在途 run 仍可能小幅突破预算
     分桶行：已验证 N / 内容价值未验证 N / 各 status 计数
     表行：实例ID | 名字 | 实际模型 | 请求模型 | 评分模型 | 状态 | 缓存 | 完整题数 | 分差 | 判定 | 本次花费 -->

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
> 按 Agent 分组；已确认、推断/未知、已排除不混写。

## <agent>（<n> 个实例）
- <runtime_name>（<component_type>，<accounting_status 中文>，30 天用了 <usage> 次）
<!-- INJECT: 仅补场景建议（什么时候会用到它），不改脚本生成的实例与状态 -->
```
