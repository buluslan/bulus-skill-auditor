<div align="center">

<img src="assets/banner.png" alt="skill 体检大师 banner" width="100%">

# 🩺 skill 体检大师

**给你的 skill 库做一次全身体检，揪出白烧钱和该退役的家伙**

**想了解更多最新AI行业动态,AI+电商/广告的行业实践方法,人与AI如何协作共生的思考,请关注公众号:【新西楼.AI】**

![qrcode_for_gh_e3b954bd3859_258](https://github.com/user-attachments/assets/d8f068d9-c4f8-46c7-914c-fbcab5d52f2a)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.2.1-black.svg)]()

**按 Agent 三笔 Token 估算 · 四类诊断 · 对比评测 · 改造优先于删除 · 跨 Agent**

**Created By Buluu@新西楼.AI**

</div>

---

## 项目简介

skill 体检大师（bulus-skill-auditor）是由 **buluslan（公众号：新西楼.AI）** 研发的 skill 库体检与治理工具。

你输入本机的 skill 库，它会按 Agent 识别当前可见或可保守推断的 skill、command 与 agent 组件，把常驻、触发和参考文件三笔 token 估算分别列账，再结合重复度、结构和可用的近期直接使用记录做诊断；经你确认预算后，它还能运行“带 skill / 不带 skill”的对比评测，最后输出带统计口径、证据状态、复核线索和瘦身建议的报告。

| 它读取 | 它检查 | 你得到 |
|---|---|---|
| SKILL.md、明确声明的组件、可用的本地直接使用记录 | 按 Agent 的三笔 token 估算、重复内容、结构负担、近期使用、可选对比评测 | 已确认清单、推断候选、排除项、证据与改造建议 |

> [!TIP]
> **更多 AI 实战内容，请关注公众号「新西楼.AI」**

作为 **Agent 原生** 工具，它已适配 Claude Code 与 Codex，并提供实验性的 Hermes 适配器；其他 Agent 可通过新增适配器接入。**只建议不动手**——它不会删除、修改或移动被审计对象，所有处置都留给你确认。发现证据不完整时，报告会明确写“已确认清单 + 推断候选”，不会把推断包装成当前全量。

**为什么你需要它：**

- skill 越装越多，常驻简介、触发正文和参考文件到底各占多少，没有统一账单。
- 同名、改名或跨 Agent 的副本容易重复维护，也可能重复占用上下文。
- 模型升级后，老 skill 的一部分能力可能已经变成模型常识，需要重新验证内容价值。
- “近期没用”不等于“应该删除”；更稳妥的顺序是先看证据，再决定保留、改瘦或停用。

## ✨ 它做什么

| 体检项 | 口径 | 回答的问题 |
|---|---|---|
| **按 Agent 三笔 Token 估算** | 常驻、触发、参考文件分别估算；已确认、推断与排除项分开 | 每个 Agent 当前确认的负担是多少？哪些只是候选？ |
| **发现证据** | 优先使用运行时探测或管理命令；失败时保守降级 | 这个组件为什么被列入？它是已确认还是推断？ |
| **使用统计** | 只认直接调用或技能文件加载事件，未知与歧义单列 | 最近确实用了哪些？哪些记录无法唯一归属？ |
| **四类诊断** | 重复、疑似原生覆盖、超重、健康 | 谁值得优先复核？依据是什么？ |
| **对比评测** | 同一案例比较带 skill 与不带 skill；只在用户批准后运行 | 这个 skill 的内容价值是否已被当前模型覆盖？ |
| **治理建议** | 改造优先于删除，结论附证据状态 | 该保留、改瘦、继续验证，还是人工停用？ |

对比评测只有在原始结果完整、两臂可比较、模型明确且没有跳过付费评分时，才会给出内容价值结论。部分结果、运行错误、未知 schema 或模型不一致会保留证据，但状态只能是“无结论”或“内容价值未验证”。

## 📊 用了之后是什么效果（真实机器实测）

先说背景：AI 每次开新对话，都会先把你装的所有 skill 的「名片」（名字 + 一句话简介）过一遍，才知道该叫谁来干活。这片名片区有容量上限——Claude Code 大约 2,000 token（token 是 AI 的字数计量单位，1 token 约半个到一个汉字）。

**名片装不下会怎样？系统不会报错，只会默默把后面的丢掉。** 也就是说：装太多 skill，排在后面的 skill 简介等于白写了，AI 根本不知道它存在。

下面是一台真实开发机的体检结果（2026-09-23，已脱敏）：装了 Claude Code 和 Codex 两个 AI 工具、共 352 个 skill 组件，跑完只用了 4 秒。扫出来五件事：

**1️⃣ 四分之三的名片是白写的。**
Claude Code 里 140 张名片要占 8,885 token 的地方，但名片区只有约 2,000——**四分之三的简介根本挤不进去，被默默丢掉了**。你可能精心给每个 skill 写了介绍，但 AI 压根没看到。

**2️⃣ 近九成装了就没动过。**
过去 30 天：Claude Code 的 140 个里有 123 个一次都没被调用（87.9%）；Codex 的 212 个里有 181 个（85.4%）。它们不占对话空间的名额，但每一个都值得问一句：还留吗？

**3️⃣ 同一个工具装了两份。**
1,472 对「两个 AI 工具里装了同一个 skill」。这不会花双份的钱，但改了其中一份、忘了另一份，两边就会悄悄不一样。

**4️⃣ 有的 skill 一被叫醒就塞爆对话。**
最重的一个，每次被调用就往对话里塞 3.2 万 token 的说明书——相当于每次都先读一本 60 页的手册再干活。还有个 skill 的随身资料库高达 32 万 token。

**5️⃣ 真正常用的其实就几个。**
比如 `lark-doc` 30 天用了 13 次——这种才是真刚需，重点保护。体检报告会帮你把这极少数「真在用的」和一大片「装了没动的」清楚分开。

**报告的总览长这样（每个 AI 工具各算各的，绝不混成一笔账）：**

| 装在哪 | 扫描状态 | 确认在用 | 简介总需求 | 名片区容量 | 装不下的部分 |
|---|---|---|---|---|---|
| Claude Code | 完整 | 140 个 | 8,885 | 约 2,000 | **6,885** |
| Codex | 完整 | 212 个 | 15,201 | 无公开上限，不乱估 | 不乱估 |

**每个 skill 的三笔账长这样（节选）：**

| skill 名字 | 每次都挂着 | 一用就塞进来 | 随身资料库 | 30天用了几次 |
|---|---|---|---|---|
| skill-production-factory | 362 | 3,068 | 6,172 | 2 次 |
| lark-sheets | 292 | 7,837 | **116,513** | 0 次 |
| lark-doc | 120 | 951 | 49,452 | **13 次** |
| design-review | 33 | **32,310** | 0 | 0 次 |
| frontend-design | 74 | 767 | 0 | 2 次 |

同一张表能看出完全不同的处境：`lark-doc` 高频在用（13 次）是重点保留；`lark-sheets` 零使用 + 随身带了 11 万 token 资料库，是瘦身首选；`design-review` 一用就塞 3.2 万 token 说明书，该把正文拆成按需翻的资料；`frontend-design` 正文只剩个空壳，是写漏了内容。

拿到这些事实之后，删哪个、留哪个、怎么改瘦，决定权全在你——工具只给证据，不动手。

完整报告（500 行，含全部组件明细、重复名单、复查命令）见 **[docs/example-report.md](docs/example-report.md)**。它本身就是用仓库里的脱敏工具生成的：本机路径全部替换成了 `<local-path>`，你可以拿它对照检验脱敏效果。

## 🚀 安装

macOS / Linux 可直接复制执行：

```bash
git clone https://github.com/buluslan/bulus-skill-auditor.git
cd bulus-skill-auditor
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Windows PowerShell：

```powershell
git clone https://github.com/buluslan/bulus-skill-auditor.git
Set-Location bulus-skill-auditor
py -3.9 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

若要通过对话触发，把仓库放进当前 Agent 的 skills 路径。也可以完全不安装为 skill，直接运行下面的本地脚本。

## 💬 对话触发

```text
帮我审计一下我的 skills       # 免费体检，通常几分钟
生成一份我的 skill 清单        # 已确认、推断与排除项分开
深度审计，预算 3 美元以内       # 先给计划和预算，你确认后才启动评测
新模型发布了，重新扫一遍       # 静态内容未变时复用可验证缓存，模型变化会失效
```

实际耗时取决于已安装组件数量、本地使用记录规模和当前 Agent 的发现能力。免费层通常需要几分钟；深度评测的耗时与费用由案例数、运行次数和模型决定。

## 🧰 只运行脚本

下面三条命令会生成清单、计量结果和 Markdown 报告骨架：

```bash
OUT=./skill-audit-output
python3 scripts/collect.py --out-dir "$OUT"
python3 scripts/measure.py "$OUT/00-inventory.json" --out "$OUT/01-metrics.json"
python3 scripts/render_report.py \
  --inventory "$OUT/00-inventory.json" \
  --metrics "$OUT/01-metrics.json" \
  --out "$OUT/03-report.md"
```

> [!IMPORTANT]
> **只运行脚本得到的是可复现的报告骨架，不是完整人工判断。** 数量、token、状态和表格由脚本生成；诊断叙述、处置取舍与最终建议仍需要 Agent 或人工根据证据补充。没有运行深度评测时，内容价值应保持“未验证”。

### 可选：运行深度评测

Claude Code 路由必须显式给出真实执行模型；judge 模型只有在你明确指定时才传入：

```bash
python3 scripts/evaluate.py \
  --skills <instance-id-1,instance-id-2> \
  --inventory "$OUT/00-inventory.json" \
  --out-dir "$OUT" \
  --runtime-agent claude-code \
  --model <execution-model> \
  --max-cost-usd <single-skill-start-limit> \
  --total-budget-usd <total-start-limit>
```

如需固定 judge，再额外添加：

```text
--judge-model <judge-model>
```

`--model` 是实际执行参数，不是报告标签；报告里的实际模型仍从原始评测结果推导。评测固定 `concurrency=1`。总预算是**后续任务的启动上限**，不是对单个已经在途任务的强制截断，因此最后一个在途任务可能让实际费用小幅超过启动上限。非 Claude Code 或无法可靠识别的运行时会以 `$0` 输出 `unsupported_runtime`，不会因为 PATH 中碰巧存在 `claude` 就启动付费命令。

## 🔐 生成可分享的脱敏副本

本地原始产物会保留绝对路径，方便复核。分享前对**整个输出目录**生成新的脱敏副本：

```bash
python3 scripts/redact_report.py "$OUT" --out "${OUT}-share"
```

该命令不会原地修改原始目录；它会递归处理 JSON、JSONL、Markdown 和其他 UTF-8 文本中的 macOS、Linux、Windows 用户路径，包括 `source_file`、`source_realpath`、插件安装路径、使用记录来源和评测原始结果路径。输出目录必须位于输入目录之外且尚不存在；遇到无法安全处理的二进制文件或符号链接时会停止，而不是静默生成可能泄漏路径的副本。

也可以继续处理单个文件：

```bash
python3 scripts/redact_report.py \
  "$OUT/00-inventory.json" \
  --out "$OUT/00-inventory.share.json"
```

## 🧠 它怎么判断

- **发现层**：优先采用 Agent 的运行时证据和只读管理命令。已启用的当前插件、运行时明确暴露的组件才进入已确认账单；推断候选单列，禁用、旧版本、未声明目录和仅缓存存在的项目不冒充已启用。
- **免费层**：按 Agent 分开计算常驻、触发、参考文件三笔估算，再检查重复、结构和严格的直接使用事件。使用数据不可用时写明限制，不把“未知”当成“零使用”。
- **深度层**：先根据可审计性与证据状态筛选候选，再按用户批准的模型、运行次数和启动预算运行对比评测。缓存同时绑定内容、案例、评分器、模型、运行次数、评测模式、Claude Code 版本和结果 schema；任一变化都会失效。
- **结论层**：完整且可判分的结果才进入“已验证”。部分结果、错误、跳过评分、缺臂、缺案例、未知模型或未知 schema 单独列出，不重建正式分差。

与官方 `/doctor` 的关系：官方工具关注安装与运行健康，本工具关注跨 Agent 的内容负担、证据状态和治理建议。两者互补；重叠指标以各自公开口径呈现，不混成一个数字。

## 📦 输出文件

| 文件 | 内容 |
|---|---|
| `00-inventory.json` | 组件身份、来源、活跃证据、发现覆盖、结构化问题与使用记录 |
| `01-metrics.json` | 按 Agent 的已确认/推断/排除统计、三笔 token 估算、重复与优先级 |
| `02-eval-results.json` | 本次请求的评测状态、实际模型、案例、费用与原始证据路径 |
| `03-report.md` | 面向人的报告骨架；完整建议需要 Agent 或人工补充 |

三个 JSON 文件使用 `schema_version: "2.0"` 和各自的 `schema_name`。未知 major 必须显式报不支持；旧版输入可以兼容读取，但旧版无法证明当前活跃性的内容只能按“推断/未知”展示。字段与判定口径见 [CONTRACT.md](CONTRACT.md)。

## 🛡️ 只读与隐私边界

- 被审计的 skill 目录、会话记录、Agent 配置和插件缓存始终只读；只写 `--out-dir` 及其临时副本。
- 管理命令仅用于读取当前状态。命令本身可能按各自产品行为刷新市场状态，但审计器不会直接发起外部 HTTP 请求。
- 配置降级只读取插件与市场的白名单字段；provider、凭证、完整环境变量和整段配置不会进入 JSON、warning 或报告。
- 所有删除、移动、停用与内容改写都只是建议，必须由你人工确认和执行。

## 📁 结构

```text
bulus-skill-auditor/
├── SKILL.md              # 对话入口与执行边界
├── CONTRACT.md           # v2.0 公共数据契约
├── docs/
│   └── example-report.md # 真实机器的脱敏示例报告
├── scripts/
│   ├── collect.py        # 发现组件并汇总直接使用记录
│   ├── measure.py        # 三笔 token 估算、重复与优先级
│   ├── render_report.py  # 确定性报告骨架
│   ├── evaluate.py       # 预算受控的对比评测
│   ├── redact_report.py  # 生成不改原件的脱敏分享副本
│   ├── usage.py          # 严格的直接事件解析
│   └── adapters/         # Claude Code / Codex / Hermes 适配器
├── references/           # 审计、出题、治理与报告判读
└── evals/                # 评测案例
```

## 🏠 交流社区

<div align="center">

🎯 **更多 AI 实战教程和专属福利尽在我们「MBG 跨境AI实战圈」,已有 50+ 跨境大卖、AI 专家热聊中**

—— 欢迎跨境电商从业者加入我们,一起探索 AI+商业的最佳实践和真实边界,跑通【跨境AI】的从 0 到 1,打败你的同事,干掉你的老板。

**社区介绍:[my.feishu.cn/wiki/WNi0wh3mIiOLhzkCLFPcwUr9nrg](https://my.feishu.cn/wiki/WNi0wh3mIiOLhzkCLFPcwUr9nrg)**

<img width="1125" height="618" alt="image" src="https://github.com/user-attachments/assets/20f47cd6-e33c-4f3e-9362-3846c11135fd" />

</div>

## 📜 License

MIT — 随便用,欢迎 PR 扩展 agent 适配器。

---

<div align="center">

**如果这个工具帮到了你,欢迎 ⭐ Star 支持。更多 AI × 跨境电商实操内容,关注公众号「新西楼.AI」。**

</div>
