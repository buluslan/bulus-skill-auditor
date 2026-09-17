<div align="center">

<!-- <img src="assets/banner.png" alt="bulus-skill-auditor" width="100%"> -->

# 🩺 bulus-skill-auditor

**skill 体检大师 —— 给你的 skill 库做一次体检：谁在白烧钱、谁重复了、谁教的东西模型已经会了**

**想了解更多最新AI行业动态,AI+电商/广告的行业实践方法,人与AI如何协作共生的思考,请关注公众号:【新西楼.AI】**

![qrcode_for_gh_e3b954bd3859_258](https://github.com/user-attachments/assets/d8f068d9-c4f8-46c7-914c-fbcab5d52f2a)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)
[![Version](https://img.shields.io/badge/version-0.1.0-black.svg)]()

**真账单 · 四类诊断 · 原生覆盖检测 · 重构优先于删除 · 跨 Agent**

**Created By Buluu@新西楼.AI**

</div>

## 项目简介

你说一句"帮我审计一下 skills"，Skill 会扫描本机全部 agent 的 skill 库（Claude Code / Codex / Hermes），计算每个 skill 的常驻 token 成本、30 天真实使用记录和重复度，基于账单、闲置、结构、内容价值四类信号做诊断，再对拿不准的高嫌疑做"带 skill vs 裸模型"对比考试（需你确认预算）——验证它教的东西现在的模型是不是本来就会，最后输出一套带真账单、四类诊断结论、瘦身方案的完整体检报告（顺手附一份"我到底装了哪些 skill"的清单）。

**Agent 通用**：skill 是 agent 无关的指令集，本工具天然跨 agent——审计对象支持 Claude Code / Codex / Hermes（每种 agent 一个适配器，可扩展更多），本体可装进 Claude Code skills 路径（Codex / Cursor / OpenCode 用户：把 SKILL.md 当指令喂给 agent 即用）。

**为什么你需要它：**

- ❌ skill 越装越多，每个的简介每次对话都在占 token——白付了多少钱没人给你算过账
- ❌ skill 装到一定数量，列表会被**静默截断**：一部分 skill 直接从模型视野消失，你根本不知道
- ❌ 模型一直在升级，老 skill 教的东西现在可能模型原生就会——但没有任何工具判断"哪些该退役了"
- ❌ 现有清理工具只会看"多久没用过"，终点都是删——没人告诉你"别删，这样改瘦就值了"

## ✨ 它做什么

| 能力 | 说明 |
|---|---|
| **真账单** | 三笔账分开算：常驻成本（不用也在占）、加载成本（触发读 SKILL.md 才花）、参考文件成本（按需读参考文件才花）；o200k 计量（与官方 tokenizer 偏差 ≤10%）；中文 skill 计量准确——实测同类工具的估算法在中文场景**低估 70-75%** |
| **四类诊断** | 重复（含"换皮 skill"识别）/ 疑似过时（模型已原生覆盖）/ 超重 / 健康 |
| **原生覆盖检测** | 对比考试：同一道题让模型带着 skill 做一遍、裸做一遍，答卷差不多 = 它教的东西模型本来就会（附带 skill / 不带 skill 的两份原始分，可复核） |
| **重构建议** | 改造优先于删除：砍掉模型常识部分留独门核心、确定性逻辑下沉到脚本、超重正文拆成按需加载的参考文件——每条建议都附依据数据和预计收益 |
| **一份清单** | 顺手产出全量 skill 分类清单，记不起装了什么时丢给 agent 自己判断 |
| **多 Agent** | Claude Code（全功能）/ Codex（全功能）/ Hermes（设计支持），每种 agent 一个适配器、可扩展 |
| **省钱阀门** | 深度评测前先便宜预筛（一次调用三出口），只对真正拿不准的烧钱；跑前报价你点头才跑 |
| **只建议不动手** | 对被审计对象 100% 只读，处置 100% 留人工确认 |

## 🚀 快速开始

装进 skills 路径后，直接对话触发：

```text
帮我审计一下我的 skills          # 免费层：真账单 + 四类诊断 + 处置建议（分钟级）
生成一份我的 skill 清单           # 只要清单（脚本层秒级）
深度审计，预算 3 美元以内          # 含对比考试（先报价，你点头才花钱）
新模型发布了，重新扫一遍高嫌疑     # 复用考题库换新模型重考，两份答卷分差的变化 = 价值衰减信号
```

单脚本也可直接跑（免对话）：

```bash
python3 scripts/collect.py --out-dir ./skill-audit-output/    # 扫描全 agent skill 库（脚本层秒级）
python3 scripts/measure.py ./skill-audit-output/00-inventory.json --out ./skill-audit-output/01-metrics.json
python3 scripts/render_report.py --metrics ./skill-audit-output/01-metrics.json --out ./skill-audit-output/03-report.md
```

依赖：Python 3.9+，`pip install tiktoken`（仅此一个）。

## 🧠 它怎么判断

- **免费层（静态）**：扫文件算账——常驻/加载/参考文件三笔 token、使用记录（窗口数来自会话扫描，终身计数来自官方静态数据源）、Jaccard 重复度（跨 agent 换名重复也抓）、结构检查（超重无 refs / 简介超长 / listing 超预算静默截断警示）
- **深度层（付费，可选）**：先预筛（明显有独门价值的直接放行、明显是模型常识的标疑似），只对拿不准的出题考试；**出题铁律：考 skill 的私有资产（独有框架/标签/流程），不考模型原生就会的通用能力**——否则裸模型也能满分，好 skill 会被误判
- **判定矩阵**：两份答卷同分且考了私有资产 = 疑似原生覆盖（须人工复核）；带 skill 明显更好 = 有真实价值；考题无区分度 = 回炉重出，不下结论
- **数字诚实**：所有结论挂数据源 + 可自行执行的复核命令；"疑似"永远不写成"确定"

与官方 /doctor、/skill-doctor 的关系：官方管"用不用、贵不贵"（运行时用量），本工具管"写得好不好、内容还值不值"（质量 + 内容价值 + 重构建议）——互补不竞争，与官方重叠的口径（unused 三档、listing 预算）直接对齐官方源码结论。

## 📁 结构

```
bulus-skill-auditor/
├── SKILL.md              # 主入口（薄路由：模式识别 / 预算决策 / 报告缝合）
├── scripts/
│   ├── collect.py        # 多 agent 扫描 + 使用统计（双源）
│   ├── measure.py        # token 计量 / 重复检测 / 结构检查 / 优先级
│   ├── render_report.py  # 报告骨架渲染（聚合数字全部脚本算）+ 注入位
│   ├── evaluate.py       # 对比考试编排（plugin 组装 → 官方 eval → Δ 汇总 → 缓存）
│   ├── usage.py          # 会话记录使用统计（可独立跑）
│   └── adapters/         # agent 适配器：claude_code / codex / hermes
├── references/           # 判读规范：审计判据 / 出题铁律 / 重构手册 / 报告格式
└── evals/                # 测试剧本
```

## 📜 License

MIT License · Created By Buluu@新西楼.AI

## 📖 写在最后

<div align="center">

**如果这个工具帮到了你,欢迎 ⭐ Star 支持。更多 AI × 跨境电商实操内容,关注公众号「新西楼.AI」。**

</div>
