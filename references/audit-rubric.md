# 审计判据（四类诊断 + 预筛判断）

> 何时读：诊断阶段（Agent 拿 01-metrics.json 判四类时）与预筛阶段（evaluate 流程里判断哪些 skill 值得进深度评测）。
> 代码化的阈值在 scripts/ 里（CONTRACT.md「判定阈值」节），本文件是判据的语义规则与 Agent 判断规范。结论必须挂数据（反空话原则：没有数据支撑的结论不写），"疑似"不许写成"确定"（用户掌舵原则：疑似不写成确定，判断交用户）。

## 四类诊断判据

### ① 重复（duplication）
- **机器信号**：Jaccard ≥ 0.55（CONTRACT 阈值）；跨 agent 同名/同 description 是换皮信号
- **Agent 判断**：看重复对的双方 description+body 开头，判断是真功能重叠还是仅措辞相似（同领域不同用途很常见）。真重叠 → 给合并方向（R5）；仅相似 → 降为"低置信"，不进诊断主表
- **结论级别**：重复结论 = **需人工确认**（换名重复要留证据：两方的关键句对照）

### ② 过时 / 模型已原生覆盖（stale）
- **两个层级，别混**：
  - 行为级（便宜）：30 天 0 激活 + 使用数据覆盖正常 → 只能说"疑似闲置"，**不能**说"过时"——闲置可能是触发词失配（R6）
  - 语义级（贵，eval）：见下方预筛+评测。只有 Δ≈0 且 case 过难度门槛才可判 suspected_native_coverage
- **禁句**："这个 skill 没用了"。**改说**："在 <模型版本> 上，带与不带它做 <case 名> 的得分都是 <x>/<y>，它教的 <核心主张> 疑似已被模型原生覆盖（建议人工复核 case 是否考出差异）"

### ③ 超重 / 结构问题（heavy）
- **机器信号**：structure_flags（oversized_description / heavy_body_no_refs / skeleton）
- **Agent 判断**：对照 refactor-playbook R3/R4 给具体拆法；listing 超限要置顶警示（静默截断风险）

### ④ 健康（healthy）
- 无重复信号、无结构 flag、使用正常 → 归此类，报告里一句带过数量，不逐个展开（报告密度留给有问题的）

## 预筛判断规范（深度评测的阀门，每 skill 一次便宜判断）

Agent 读该 skill 的 description + SKILL.md 全文，回答一个问题：**"它教的东西，现在的模型是不是默认就会？"** 三出口：

| 出口 | 判据 | 去向 |
|---|---|---|
| `likely_valuable` | 有独占资产：私有数据/特定阈值与流程/领域深知识/品牌规范/工具编排——裸模型明确做不好 | 不进 eval 队列（省钱），报告标"预筛有价值" |
| `likely_native` | 内容主要是通用最佳实践、常识性流程、模型时代前的提示词工程（"要仔细""分步骤问"类） | 标"疑似原生覆盖（预筛）"，**不直接定罪**；用户可选 1 个确认 case 验证 |
| `uncertain` | 介于两者（有部分独占内容但占比存疑） | 进 eval 队列，按优先级排序烧钱 |

判断时禁止只看名字和 description 就下结论——**必须读 body**（名字像过时的可能内容很新，反之亦然）。预筛结论必须附一句依据（"它包含 <具体独占内容>"）。

## 深度评测判定映射（读 02-eval-results.json 时）

见 case-authoring.md「判定与证据链」表。报告呈现时 Δ 附 with/without 原始分，verdict 用 suspected_* 前缀（疑似），处置交用户。

## 官方口径对照（官方文档与本地验证结论；调研底稿存内部研发仓库，不随本包发布）

**该抄的口径**（我们与官方重叠的部分直接对齐，用户看到一致的数字）：
- **unused 三档**：①终身 0 次（`~/.claude.json` skillUsage.usageCount === 0 且在 listing 中 = 硬信号"never invoked"）②窗口 0 次（lastUsedAt + transcripts 判定）③disused（14 天 + 10 会话双门槛，防低频用户误杀——plugin 专用）。我们的 R6 处置引用这套档位
- **listing 成本口径**：常驻成本 = `- name: description` **一行**的 token（官方估算 chars/4；我们用 o200k 更准但量级一致，报告中注明口径）；description 硬上限 **1536 字符**（超了违规）；listing 总预算 = 上下文 × 1%（200k → ~2000 token / 8000 字符），超预算 = 静默截断 = 路由退化；注意我们的 always 只计 description（不含 name），比官方一行口径系统性偏低，报告口径声明已注明——叙述时别写成"与官方数字一致"
- **优先级公式**（我们 measure.py 实现：always 归一×0.5 + 少用程度×0.3 + body 重度×0.2；官方参考公式：`usageCount × max(0.5^(daysSinceLastUse/7), 0.1)`，用于官方截断顺序，报告引用官方口径时用）。**呈现规矩：priority 分数必须与 reasons 同现**——只给分数不给理由 = 退化成笼统评分，违反原则五
- **"终身 0 次"口径分侧（首轮对抗审查修正）**：claude-code 侧无 skillUsage 条目 = **推断**终身 0（官方硬信号原文是"条目存在且 usageCount===0"；实测条目只在用过时写，"无条目"是我们从缺失推断的）——报告表述用"无 skillUsage 条目（推断终身 0）"；codex 侧没有终身计数数据源，只能标"窗口 0 激活、无终身数据源"，**禁止**与 claude-code 侧合并表述成统一"官方硬信号"
- **frontmatter 坏 = 字段全丢**：官方静默行为——name 回退目录名、description 回退正文首行（模型拿散文做路由匹配！）、allowed-tools 等全失效，零警告。我们的 collect 把这作为高价值检查项
- **报告纪律**：官方每项强制 verdict（禁止 "up to you"）、估算标 "est."、改动逐文件附撤销方式——我们的报告继承这套纪律

**要错开的定位**（差异化声明，进 README）：
- /skill-doctor 官方自认 **"不是 linter"**——官方管"用不用、贵不贵"（运行时用量），我们管"写得好不好、内容还值不值"（SKILL.md 质量 + 模型原生覆盖 + 重构建议）。互补不竞争
- 窗口使用数据（30 天 transcripts 扫描）我们也算，但标注口径"来自 transcripts 扫描，30 天"，不与官方 /skill-doctor 的运行时用量口径混淆；终身计数静态取 skillUsage，不包装成官方运行时数据
- 官方 skillOverrides 四态（on / name-only / user-invocable-only / off）是现成的处置动作词汇表——R6 的建议直接引用这套状态，不自造开关
