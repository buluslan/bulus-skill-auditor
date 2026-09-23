# 重构手册（处置建议的规则库）

> 何时读：生成处置建议时（报告缝合阶段）。核心理念：**重构 > 删除**——现有工具的终点都是删，我们的差异化是"别删，这么改"。
> 每条建议必须：挂诊断信号（为什么建议这个）+ 带预计收益（能省多少，数据从 01-metrics.json 来）+ 带"建议人工确认"标注。禁止替用户执行。

## 规则清单（按触发信号索引）

### R1 · 知识密度分层（针对"过时/疑似原生覆盖"）
- **触发**：eval 判 suspected_native_coverage（Δ≈0 且 case 过难度门槛）
- **建议**：不是删，是"剥壳"——skill 内容里属于模型常识的部分砍掉（通常 60-80%），只留差异化核心（私有数据/特定阈值/独特流程/品牌规范）。剥完重新计量，常驻成本可降一个数量级
- **句式**：`这个 skill 别删：它的 X/Y 部分现在的模型原生就会（eval 两份答卷 1.0/1.0），但 Z 部分（<具体内容>）仍有独占价值。建议砍成 <N> 条规则，预计常驻成本从 <a> 降到 <b> token`
- **反例**：整 skill 保留（继续白付钱）或整 skill 删除（丢掉 Z）

### R2 · 逻辑移出主循环（针对"重且带确定性逻辑"）
- **触发**：body 里有大段可代码化的判定/计算（阈值、公式、格式转换）
- **建议**：确定性逻辑下沉到 scripts/（代码算，零 token），SKILL.md 只留"何时调脚本 + 怎么读结果"。PT2.0 教案：6 条规则 + 代码化的 Light 版反而比大而全版效果好
- **收益算法**：迁移段落 token 数 × 触发频率

### R3 · 大 body 拆 refs（针对 heavy_body_no_refs）
- **触发**：body > 8000 token 且没有 references/
- **建议**：按"每次触发都需要的（留 body）/ 分支才需要的（拆 refs 并写明何时读）"二分。SKILL.md 保持路由性质
- **收益**：on_trigger 成本降幅 = 拆出量

### R4 · description 瘦身（针对 oversized / listing 超预算）
- **触发**：description > 1024 字符；或 listing 超预算——**按 Agent 分账**：claude-code 的 confirmed listing demand（active+listing confirmed 组件的 always 之和）> 2000 token（= 200k 上下文 × 1% ≈ 官方 8000 字符预算）。超预算会被静默截断——排在后面的 skill 直接从模型视野消失。inferred/unknown 组件的 token 单列（potential demand），不混进 confirmed 判定；其他 Agent 无同单位预算，写"无可比 token 上限"，不猜
- **建议**：description 只留"干什么 + 何时触发"，营销文案移 README；中文触发词保留（触发靠它）
- **注意**：常驻成本 = 该 Agent 内 confirmed 组件的 description 之和（**绝不跨 Agent 求和**），砍一个最肥的比砍十个瘦的管用（找 metrics 里该 Agent always 最大的）

### R5 · 合并重复（针对 duplication 高对）
- **触发**：Jaccard ≥ 0.55 的对。**先分两类，措辞不同**：
  - **跨 Agent 对（cross_agent_maintenance_copy）**：同一内容装在两个 Agent——这是安装/发布维护副本，**不写成"每次会话省 <n> token"**（两个 Agent 各自的 listing 账单独立，合并只减维护成本）。建议措辞：`A（claude-code）与 B（codex）内容重叠 <x>%：维护两份会双倍 upkeep，建议单一源 + 发布管道同步，消除"改一处漏一处"风险`
  - **同 Agent 对（same_agent_possible_duplicate / name_conflict）**：同一 Agent 内的物理重复/换名重复才是单会话可省的；功能重叠给合并方案（以知识密度高的为主体，吸收另一个的独有段，被并方退役）；同 skill 多副本（symlink 之外的物理重复）给去重保留一份
- **通用红线**：重复对只是候选，不自动合并、不删除、不决定 precedence；引用组件用 canonical instance_id（同 Agent 同 runtime_name 的多实例都保留）
- **句式（同 Agent 物理重复）**：`A 与 B 重叠度 62%（Jaccard），A 的 X 段独有、B 的 Y 段独有。建议以 A 为主体并入 Y，B 退役。预计每次会话省 <n> token`

### R6 · 无效曝光处置（针对 activations=0 且优先级低）
- **触发**：30 天窗口内 0 激活 + 常驻成本可观，**且该 Agent 的 usage coverage=complete**（usage_stats 为 null = 使用情况未知，不适用本条）
- **建议**：分两种——①coverage=complete 但从未触发 → 疑似触发词失配（description 与实际说法对不上），先修触发词再观察一轮，别急着删；②确认不需要 → 建议禁用/移出 skill 根（保留目录备份，给出移出命令让用户自己执行）
- **红线**：coverage 非 complete（partial/unavailable）或 usage_stats=null 时不下"无用/零激活"结论，标注"数据不足，建议观察"——未知不按零使用

## 统一输出格式（报告里每条建议）

```
[R<n>] <skill 名>：<一句话建议>
- 信号：<触发它的诊断数据，如 "always 412 tok / 30 天 0 激活 / Jaccard 0.62">
- 预计收益：<具体数字>
- 风险与前提：<什么情况下别这么做>
- [ ] 建议人工确认后执行（工具不代劳）
```

## 来源与依据

- 知识分层与逻辑下沉的反直觉效应：把确定性逻辑移出正文、只保留少量核心规则的"轻量版"，实测比大而全版本效果更好且更省——R1/R2 的方法论基础
- "skill 会不断长回来"（dev.to 公开复盘）：一次性清理无效，建议给出的是可持续结构（拆 refs/降常驻），不是一次性删减
- 静默截断机制（官方 issue #13099）：R4 的紧迫性来源——超预算不是"变慢"是"消失"
