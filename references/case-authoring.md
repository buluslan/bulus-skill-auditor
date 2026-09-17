# Case 出题规范（内容价值层 · eval 测试题的命脉）

> 何时读：对一个 skill 生成 eval case 时（evaluate.py 流程中 Agent 读本文件再出题）。
> 为什么这份规范存在：**case 质量决定"模型已原生覆盖"判定的生死**。case 出得太水，裸模型也能 pass，不带 skill 的那份答卷满分 → 好 skill 被误判成"过时"（误杀）。本规范防的就是这个。

## 铁律一：难度门槛（考私有资产，不考通用能力）

case 必须是**"不带 skill 的裸模型大概率做不好"的任务**。出完题自问：一个没有这个 skill 的普通模型，凭预训练常识能把这题做到 PASS 吗？
- 能 → 题废了，重出（这题测不出 skill 的价值）
- 不能 → 合格候选

**实操判别（首轮实测，2026-09-17）**：从 skill 的**私有资产**出题——它独有的框架名/标签体系/特定流程/专有数据结构（如 review-analyzer 的 22 维标签、异常信号卡），不从"通用能力"出题（结构化分析/分点总结/仔细认真——这些裸模型原生就会）。首轮对照组实证：考"会不会结构化分析"的 case，裸模型满分，Δ=0，好 skill 险被误判——这个坑极易踩：考题角度稍有偏差，测到的就是通用能力而不是 skill 的独有价值。

## 铁律二：对照判据，不对照文风

grader 判的是**结构性特征**（维度覆盖/归因深度/可行动性），不是"像不像 skill 的模板"。裸模型恰好用类似结构也算它赢——我们要测的是能力差，不是格式差。

## 出题流程（对单个 skill）

1. 读 SKILL.md（+核心 references），列出 2-3 条**差异化主张**（它教了什么模型默认不会/做不好的东西）
2. 每条主张设计 1 个任务：给真实感输入（数据/场景），要求完成主张覆盖的任务
3. 写 grader：PASS 条款写具体（"至少覆盖 N 个维度中的 M 个"），FAIL 模式写清楚（"泛泛总结/直接跳实现"）
4. 自查铁律一，过不了重写
5. 人审：case 入库前由用户过目（生成 ≠ 采纳）

## grader 设计规范（工程约束）

- **零成本 grader 优先**：能 regex（输出含特定结构标记）/ file_exists / tool_used 判的，不用 llm
- **llm grader 只判短输出**：判"有没有结构特征"，不判长文质量；PASS 条款逐条列出（"PASS if 至少 N 项中的 M 项"），FAIL 写明确模式（"FAIL if 泛泛总结/直接跳实现"）
- **tool_used: Skill 标 `arm: with-only`**：它是"skill 被触发"的指示器，只在带 skill 的那份答卷里生效，不参与两份答卷的对比评分（官方机制，否则不带 skill 的那份必挂、Δ 虚高）
- **judge 误判防范**（官方文档警告）：`tool_used: Skill` 过了但 Δ 为负 → 先怀疑 judge 再怀疑 skill。对策：重要结论需确认时，在 `.eval-tmp` 的 pkg 目录用官方 CLI 原生命令手工复跑一次：`claude plugin eval . --judge-model sonnet`（该参数由官方 CLI 支持，本脚本的 evaluate.py 不透传）

## 判定与证据链（首轮实测校准版）

| 信号 | 判定 |
|---|---|
| with ≈ without（双高分）且 case 只考了通用能力 | **inconclusive**——case 区分度不足，回炉重出（考私有资产）；禁止在此 case 上下"原生覆盖"结论 |
| with ≈ without（双高分）且 case 考了私有资产（grader 验了私有框架特征）仍平 | **suspected_native_coverage**（疑似模型已原生覆盖）——附 case 名与两份原始分，供人工复核 |
| with 明显 > without | **valuable**（skill 有真实边际贡献） |
| 两份答卷都低分 | **inconclusive**——case 或 grader 出问题，回炉 |
| with 低 without 高 | 反常，查 judge / 查 skill 是否干扰了模型 |

自检顺序：先确认 case 考的是私有资产（铁律一），再看 Δ。case 不合格时 Δ 无意义。

## case 库管理

- 本地存储：`<out-dir>/cases/<skill-id>/`（prompt.md + graders/，即官方 eval 目录格式，可复跑）
- 每个 case 文件头记录：针对的差异化主张、生成日期、人审状态（pending/approved）
- **新模型发布重扫**时直接复用库里的 case（同一批题换新模型重考，Δ 变化即价值衰减信号）
- skill 自带 evals/ 目录的（skill-creator 造的），直接用它的，不重复出题（先复制/改写成 `<out-dir>/cases/<skill-id>/<case名>/prompt.md + graders/` 的布局，脚本只认这个位置）
