<div align="center">

<!-- Banner: 把一张 banner 图放进 assets/banner.png 后,去掉下一行的注释即可显示 -->
<!-- <img src="assets/banner.png" alt="bulus-skill-auditor" width="100%"> -->

# 🩺 skill 体检大师

**给你的 skill 库做一次全身体检，揪出白烧钱和该退役的家伙**

**想了解更多最新AI行业动态,AI+电商/广告的行业实践方法,人与AI如何协作共生的思考,请关注公众号:【新西楼.AI】**

![qrcode_for_gh_e3b954bd3859_258](https://github.com/user-attachments/assets/d8f068d9-c4f8-46c7-914c-fbcab5d52f2a)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.0-black.svg)]()

**真账单 · 四类诊断 · 对比考试 · 改造优先于删除 · 跨 Agent**

**Created By Buluu@新西楼.AI**

</div>

---

## 项目简介

skill 体检大师（bulus-skill-auditor）是由 buluslan（公众号：新西楼.AI）研发的 skill 库体检工具，他会扫一遍你装在 Claude Code、Codex、Hermes 里的全部 skills，算出每个 skill 的真实花销、查出谁和谁重复、揪出装了没用的家伙，还会出一场"带着 skill 和裸奔对比"的考试，验证哪些 skill 教的东西现在的模型本来就会——最后输出一份带真账单、诊断结论和瘦身方案的完整体检报告。

> [!TIP]
> **更多 AI 实战内容，请关注公众号「新西楼.AI」**

作为 **Agent 原生** 工具，它适配各类 AI Coding Agent，只依赖一个 Python 库，clone 下来就能跑。**只建议不动手** —— 告诉你"哪里有问题、该改什么、能省多少"，删和改由你自己决定。每个数字都附一条你可以亲手跑的复核命令——这个赛道吹牛的工具太多，经得起对账是它的立身之本。

**为什么你需要它：**

- ❌ skill 越装越多，每个的简介每次对话都在占地方——白付了多少钱，没人给你算过账
- ❌ skill 装到一定数量，列表会被**悄悄截断**：一部分 skill 直接从模型视野里消失，你根本不知道
- ❌ 模型一直在升级，老 skill 教的东西现在可能模型本来就会——但没有任何工具告诉你"哪些该退役了"
- ❌ 现有清理工具只会看"多久没用过"，终点都是删——没人告诉你"别删，这样改瘦就值了"

## ✨ 它做什么

一句话触发，出一份多维度体检报告:

| 体检项 | 底座 | 回答的问题 |
|---|---|---|
| **真账单** | 本地精算（与官方口径偏差 ≤10%，中文也准） | 我每个 skill 每次对话白付多少钱? |
| **四类诊断** | 重复度比对 + 结构检查 + 使用记录 | 谁重复了、谁太肥、谁装了没用、谁健康? |
| **原生覆盖检测** | 对比考试：同一道题，带 skill 做一遍、裸奔做一遍 | 这个 skill 教的东西，现在的模型是不是本来就会? |
| **瘦身建议** | 六条改瘦手法（改瘦优先于删除） | 别删——砍掉模型都会的部分，留独门货，怎么改? |
| **skill 清单** | 顺手产出的分类清单 | 我到底装了哪些? 记不起来时丢给 agent 自己判断 |

**对比考试怎么读**：两份答卷差不多，说明模型已经原生会了，这个 skill 疑似过时（附两份原始分，你可以复核）；带着 skill 明显做得更好，说明它有真本事，留着。

## 🚀 快速开始

装进 skills 路径后，直接对话触发:

```text
帮我审计一下我的 skills       # 全量体检（免费，几分钟出报告）
生成一份我的 skill 清单        # 只要清单（最快）
深度审计，预算 3 美元以内       # 含对比考试（先报价，你点头才花钱）
新模型发布了，重新扫一遍       # 换新模型重考，分数变化 = 价值变化信号
```

单脚本也可直接跑（免对话）:

```bash
pip install tiktoken
python scripts/collect.py --out-dir ./skill-audit-output/          # 扫描全部 agent 的 skill 库
python scripts/measure.py ./skill-audit-output/00-inventory.json --out ./skill-audit-output/01-metrics.json
python scripts/render_report.py --metrics ./skill-audit-output/01-metrics.json --out ./skill-audit-output/03-report.md
```

## 🧠 它怎么判断

- **免费层（扫文件算账）**：每个 skill 三笔账分开算——常驻（简介每次对话都占，不用也在花钱）、加载（真被叫起来干活时读全文）、参考文件（按需去读才花）；再查重复（同一个 skill 在两个 agent 各装一份、甚至换了名字重新包装的，都认得出来）、查结构（正文超重该拆、简介超长每次多花钱、skill 列表总量超官方额度会被悄悄截断——被截掉等于白装）
- **深度层（花你的钱，先报价）**：先花小钱粗筛一遍每个可疑 skill 的内容——明显有独门本事的直接放行、明显是模型常识的标"疑似过时"；只对真正拿不准的出题考试，用两份答卷的分差说话。**出题铁律：考 skill 的独门货（它独有的框架、标签、流程），不考模型本来就会的通用能力**——否则裸模型也能拿满分，好 skill 会被冤枉
- **防冤枉三保险**：结论分级（确定/疑似/需人工确认）、每条结论附数据和复核命令、"疑似"永远不写成"确定"

与官方 /doctor 的关系：官方管"你用没用、贵不贵"，本工具管"写得好不好、内容还值不值"——互补不竞争，重叠的数字直接对齐官方口径。

## 📁 结构

```
bulus-skill-auditor/
├── SKILL.md              # 主入口（识别你要什么、控制花钱节奏、缝合报告）
├── scripts/
│   ├── collect.py        # 扫描全部 agent 的 skill 库 + 使用统计
│   ├── measure.py        # 三笔账 + 重复检测 + 结构检查 + 优先级排序
│   ├── render_report.py  # 报告骨架渲染（所有汇总数字脚本算，不手算）
│   ├── evaluate.py       # 对比考试编排（出题 → 考试 → 判分 → 存档）
│   ├── usage.py          # 聊天记录里的使用统计（可单独跑）
│   └── adapters/         # 各 agent 的适配器: claude_code / codex / hermes
├── references/           # 判读规范: 审计判据 / 出题铁律 / 瘦身手法 / 报告格式
└── evals/                # 测试剧本
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
