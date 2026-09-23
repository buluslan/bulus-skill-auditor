# Skill 审计报告 · 2026-09-23

> 口径声明（脚本固定渲染）：
> - 覆盖结论：当前全量；只有 discovery=complete 的 Agent 才能称为当前全量
> - 按 Agent 分账：不同 Agent 的 listing demand 绝不相加成一张“每次会话账单”
> - token 为 o200k_local 近似；always 只计 description，不含运行时可能附加的 name/格式开销
> - active+listing confirmed 才进 confirmed 账单；unknown/estimated 与 excluded 分列
> - 未知 usage 保持未知，不按 0 激活处理；跨 Agent 副本只表示维护关系
> - 深度评测：未运行；本次付费评测花费 $0.00

## 一、总览（按 Agent 分账）

| Agent | discovery | confirmed active | confirmed token | inferred/unknown | inferred token | excluded | excluded token | listing demand | injected upper bound | potential overflow |
|---|---|---|---|---|---|---|---|---|---|---|
| claude-code | complete | 140 | 8885 | 0 | 0 | 0 | 0 | 8885 | 2,000 / budget 2,000 | 6,885 |
| codex | complete | 212 | 15201 | 0 | 0 | 0 | 0 | 15201 | 无可比 token 上限 | 无可比 token 上限 |

说明：listing demand 是 confirmed active 的已确认需求；injected upper bound 是已知预算下最多可注入的 confirmed token；potential overflow 是 confirmed demand 超出该上限的部分。没有同单位、同口径上限的 Agent 不做猜测。
- claude-code 预算依据：Claude Code 200k context × 1% 的近似 token 上限；含推断的潜在需求=8,885、含推断的溢出=6,885


## 二、真账单（canonical instance 全量明细）

| instance | runtime | agent | type | active | listing/trigger | 常驻token | 触发token | refs | usage | priority | 标记 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| claude-code::i::bb5a72cd550a7fd84695 | skill-production-factory | claude-code | skill | active | confirmed/confirmed (confirmed) | 362 | 3,068 | 6,172 | 2 次 | 86（Agent内归一） | — |
| claude-code::i::46ef92e15526ddb9fb4c | lark-apps | claude-code | skill | active | confirmed/confirmed (confirmed) | 342 | 6,728 | 45,859 | 4 次 | 90（Agent内归一） | — |
| claude-code::i::64b466d7f3f53cab7817 | review-analyzer | claude-code | skill | active | confirmed/confirmed (confirmed) | 334 | 1,876 | 3,999 | 0 次 | 81（Agent内归一） | — |
| claude-code::i::ac797e6410363ef78f09 | lark-sheets | claude-code | skill | active | confirmed/confirmed (confirmed) | 292 | 7,837 | 116,513 | 0 次 | 90（Agent内归一） | — |
| claude-code::i::d1ef648e355d8df1e6c4 | zsxq | claude-code | skill | active | confirmed/confirmed (confirmed) | 290 | 4,318 | 55,859 | 1 次 | 80（Agent内归一） | — |
| claude-code::i::2563e95d2098b91698c2 | buluu-weekly-digest | claude-code | skill | active | confirmed/confirmed (confirmed) | 275 | 2,241 | 15,781 | 0 次 | 74（Agent内归一） | — |
| claude-code::i::2f7d2a0375001ed7ce76 | seedance-video-script | claude-code | skill | active | confirmed/confirmed (confirmed) | 218 | 2,361 | 5,860 | 0 次 | 66（Agent内归一） | — |
| claude-code::i::10ed4ccd17ccfda8d5d9 | n8n-goal-loop | claude-code | skill | active | confirmed/confirmed (confirmed) | 206 | 1,296 | 19,993 | 0 次 | 62（Agent内归一） | — |
| claude-code::i::189ab25ef344fad09494 | lark-drive | claude-code | skill | active | confirmed/confirmed (confirmed) | 204 | 6,472 | 124,750 | 0 次 | 74（Agent内归一） | — |
| claude-code::i::f6d86daf31358975cba8 | buluu-daily-brief | claude-code | skill | active | confirmed/confirmed (confirmed) | 203 | 2,377 | 11,225 | 2 次 | 62（Agent内归一） | — |
| claude-code::i::f28f854c7bb85c6e4cf8 | neat-freak | claude-code | skill | active | confirmed/confirmed (confirmed) | 197 | 3,778 | 2,771 | 0 次 | 67（Agent内归一） | — |
| claude-code::i::2b164ad2c6af2f85f8d8 | lark-wiki | claude-code | skill | active | confirmed/confirmed (confirmed) | 164 | 3,222 | 16,729 | 0 次 | 61（Agent内归一） | — |
| claude-code::i::fd26afa95a6156d44c6c | lark-slides | claude-code | skill | active | confirmed/confirmed (confirmed) | 151 | 7,598 | 320,181 | 0 次 | 70（Agent内归一） | — |
| claude-code::i::b0dc4fb030c114b499c2 | ai-intel-hub | claude-code | skill | active | confirmed/confirmed (confirmed) | 147 | 6,681 | 0 | 0 次 | 67（Agent内归一） | — |
| claude-code::i::20c7a1ffd4d737026de0 | lark-im | claude-code | skill | active | confirmed/confirmed (confirmed) | 136 | 6,258 | 80,149 | 0 次 | 64（Agent内归一） | — |
| claude-code::i::a56500f8b5d107076a11 | agentkey | claude-code | skill | active | confirmed/confirmed (confirmed) | 133 | 1,766 | 4,277 | 4 次 | 49（Agent内归一） | — |
| claude-code::i::aa6096f2b6c00e10c79f | blue-video-script | claude-code | skill | active | confirmed/confirmed (confirmed) | 133 | 2,079 | 40,856 | 0 次 | 54（Agent内归一） | — |
| claude-code::i::f77f1f05393f13226f14 | lark-base | claude-code | skill | active | confirmed/confirmed (confirmed) | 127 | 6,295 | 103,172 | 0 次 | 63（Agent内归一） | — |
| claude-code::i::79bbceaf1e0def9bad9b | n8n-code-javascript | claude-code | skill | active | confirmed/confirmed (confirmed) | 123 | 4,638 | 0 | 0 次 | 59（Agent内归一） | — |
| claude-code::i::7548e4541a67779d727d | takumi | claude-code | skill | active | confirmed/confirmed (confirmed) | 121 | 1,926 | 632 | 0 次 | 52（Agent内归一） | — |
| claude-code::i::87fa4111a03184103235 | n8n-mcp-tools-expert | claude-code | skill | active | confirmed/confirmed (confirmed) | 121 | 7,317 | 0 | 0 次 | 65（Agent内归一） | — |
| claude-code::i::a958236b3884b1749619 | lark-task | claude-code | skill | active | confirmed/confirmed (confirmed) | 121 | 3,513 | 7,932 | 0 次 | 55（Agent内归一） | — |
| claude-code::i::821d60acca1ce8d93127 | lark-doc | claude-code | skill | active | confirmed/confirmed (confirmed) | 120 | 951 | 49,452 | 13 次 | 36（Agent内归一） | — |
| claude-code::i::04fba9b234fd88886533 | logo-generator-skill | claude-code | skill | active | confirmed/confirmed (confirmed) | 116 | 1,618 | 12,799 | 0 次 | 50（Agent内归一） | — |
| claude-code::i::1e71d4b2881216c3a98d | lark-contact | claude-code | skill | active | confirmed/confirmed (confirmed) | 116 | 926 | 2,570 | 0 次 | 48（Agent内归一） | — |
| claude-code::i::8f494edd00178b4b1a6a | lark-event | claude-code | skill | active | confirmed/confirmed (confirmed) | 114 | 2,670 | 7,133 | 0 次 | 52（Agent内归一） | — |
| claude-code::i::2b28732a943c5424f53f | kami | claude-code | skill | active | confirmed/confirmed (confirmed) | 113 | 5,902 | 34,306 | 0 次 | 60（Agent内归一） | — |
| claude-code::i::ad30db48d06e235d1109 | lark-meeting | claude-code | skill | active | confirmed/confirmed (confirmed) | 113 | 3,058 | 32,719 | 0 次 | 53（Agent内归一） | — |
| claude-code::i::72621d48466c0305cd41 | n8n-workflow-patterns | claude-code | skill | active | confirmed/confirmed (confirmed) | 109 | 3,633 | 0 | 0 次 | 54（Agent内归一） | — |
| claude-code::i::a33d4fc5f33682742d57 | guizang-ppt-skill | claude-code | skill | active | confirmed/confirmed (confirmed) | 107 | 4,945 | 22,348 | 0 次 | 57（Agent内归一） | — |
| claude-code::i::30368fc664559bca4229 | n8n-code-python | claude-code | skill | active | confirmed/confirmed (confirmed) | 102 | 4,707 | 0 | 0 次 | 56（Agent内归一） | — |
| claude-code::i::cd8cb3d58eac44362be1 | lark-whiteboard | claude-code | skill | active | confirmed/confirmed (confirmed) | 99 | 734 | 3,975 | 2 次 | 44（Agent内归一） | — |
| claude-code::i::6a9b3be05439ca753330 | any2card | claude-code | skill | active | confirmed/confirmed (confirmed) | 92 | 3,855 | 4,107 | 0 次 | 52（Agent内归一） | — |
| claude-code::i::f809ac5c69906e572473 | guizang-social-card-skill | claude-code | skill | active | confirmed/confirmed (confirmed) | 91 | 5,996 | 39,528 | 0 次 | 58（Agent内归一） | — |
| claude-code::i::f946cbaa566f3b0399df | lark-calendar | claude-code | skill | active | confirmed/confirmed (confirmed) | 88 | 4,871 | 19,206 | 0 次 | 54（Agent内归一） | — |
| claude-code::i::a968ed809d314f93fb21 | n8n-expression-syntax | claude-code | skill | active | confirmed/confirmed (confirmed) | 86 | 2,608 | 0 | 0 次 | 48（Agent内归一） | — |
| claude-code::i::ef0a7db0a9f32a10dcd3 | lark-approval | claude-code | skill | active | confirmed/confirmed (confirmed) | 86 | 1,795 | 29,396 | 0 次 | 46（Agent内归一） | — |
| claude-code::i::8bb9c39064e510034a8f | lark-markdown | claude-code | skill | active | confirmed/confirmed (confirmed) | 85 | 1,230 | 6,000 | 0 次 | 45（Agent内归一） | — |
| claude-code::i::28673537f9d09372e9e9 | n8n-validation-expert | claude-code | skill | active | confirmed/confirmed (confirmed) | 84 | 4,363 | 0 | 0 次 | 53（Agent内归一） | — |
| claude-code::i::266c0147270e34432123 | lark-mail | claude-code | skill | active | confirmed/confirmed (confirmed) | 82 | 6,792 | 56,442 | 0 次 | 58（Agent内归一） | — |
| claude-code::i::3cf6ac5e254f33772a99 | lark-okr | claude-code | skill | active | confirmed/confirmed (confirmed) | 82 | 2,845 | 37,177 | 0 次 | 48（Agent内归一） | — |
| claude-code::i::2532d14e27b3bf2dd9e7 | n8n-node-configuration | claude-code | skill | active | confirmed/confirmed (confirmed) | 77 | 4,494 | 0 | 0 次 | 52（Agent内归一） | — |
| claude-code::i::1b3991bb3cc2b33663ed | e-commerce-find-skills | claude-code | skill | active | confirmed/confirmed (confirmed) | 75 | 573 | 0 | 0 次 | 42（Agent内归一） | — |
| claude-code::i::55010758b8363817e660 | frontend-design | claude-code | skill | active | confirmed/confirmed (confirmed) | 74 | 767 | 0 | 2 次 | 40（Agent内归一） | 骨架 |
| claude-code::i::403f868db48c1c40b8e3 | deepsea-ffmpeg-drama-edit | claude-code | skill | active | confirmed/confirmed (confirmed) | 73 | 1,402 | 3,528 | 1 次 | 43（Agent内归一） | — |
| claude-code::i::b2e165cefdd696d23633 | ppt-master | claude-code | skill | active | confirmed/confirmed (confirmed) | 73 | 6,109 | 36,756 | 0 次 | 55（Agent内归一） | — |
| claude-code::i::f46124537285f9087b49 | drawio | claude-code | skill | active | confirmed/confirmed (confirmed) | 72 | 1,979 | 0 | 0 次 | 45（Agent内归一） | — |
| claude-code::i::3dd81841177ae86f6f97 | skill-publish | claude-code | skill | active | confirmed/confirmed (confirmed) | 70 | 1,390 | 7,922 | 3 次 | 40（Agent内归一） | — |
| claude-code::i::d73660fdea97ebc18620 | lark-openapi-explorer | claude-code | skill | active | confirmed/confirmed (confirmed) | 69 | 1,379 | 0 | 0 次 | 43（Agent内归一） | — |
| claude-code::i::6efaca321fd439bcb016 | find-skills | claude-code | skill | active | confirmed/confirmed (confirmed) | 63 | 1,047 | 0 | 0 次 | 41（Agent内归一） | — |
| claude-code::i::9ff311d50dcdb2e3d37f | skill-creator | claude-code | skill | active | confirmed/confirmed (confirmed) | 60 | 8,327 | 19,278 | 3 次 | 55（Agent内归一） | — |
| claude-code::i::56ef84b0fe2bf481708e | mindcode-claw-image2 | claude-code | skill | active | confirmed/confirmed (confirmed) | 56 | 1,166 | 0 | 0 次 | 41（Agent内归一） | — |
| claude-code::i::3938ef96e4653becbfff | wechat-crawler | claude-code | skill | active | confirmed/confirmed (confirmed) | 55 | 424 | 483 | 3 次 | 36（Agent内归一） | — |
| claude-code::i::44df5ecbdeec0274bb4a | brainstorming | claude-code | skill | active | confirmed/confirmed (confirmed) | 51 | 2,428 | 0 | 7 次 | 36（Agent内归一） | — |
| claude-code::i::6e473d96e7c9762cf268 | lark-workflow-meeting-summary | claude-code | skill | active | confirmed/confirmed (confirmed) | 47 | 1,976 | 0 | 0 次 | 41（Agent内归一） | — |
| claude-code::i::2298054f54b1afb60874 | diagram | claude-code | skill | active | confirmed/confirmed (confirmed) | 46 | 4,083 | 0 | 0 次 | 47（Agent内归一） | — |
| claude-code::i::7cb5d6e8989bf3560068 | lark-workflow-standup-report | claude-code | skill | active | confirmed/confirmed (confirmed) | 44 | 1,355 | 0 | 0 次 | 39（Agent内归一） | — |
| claude-code::i::f4a24b93bf657f9483de | lark-shared | claude-code | skill | active | confirmed/confirmed (confirmed) | 44 | 1,088 | 3,582 | 0 次 | 39（Agent内归一） | — |
| claude-code::i::124471636c7f759e3fe7 | agently-mail | claude-code | skill | active | confirmed/confirmed (confirmed) | 43 | 2,979 | 0 | 0 次 | 43（Agent内归一） | — |
| claude-code::i::58ebca4f8014d6e91320 | design-consultation | claude-code | skill | active | confirmed/confirmed (confirmed) | 41 | 17,236 | 0 | 0 次 | 56（Agent内归一） | 超重无refs |
| claude-code::i::e05f2a4609bfe7006d85 | lark-skill-maker | claude-code | skill | active | confirmed/confirmed (confirmed) | 40 | 660 | 0 | 0 次 | 37（Agent内归一） | — |
| claude-code::i::89e19bae4060f294d112 | web-design-guidelines | claude-code | skill | active | confirmed/confirmed (confirmed) | 39 | 191 | 0 | 0 次 | 36（Agent内归一） | 骨架 |
| claude-code::i::5e15c1625fbd29b46d80 | verification-before-completion | claude-code | skill | active | confirmed/confirmed (confirmed) | 38 | 925 | 0 | 0 次 | 38（Agent内归一） | — |
| claude-code::i::d66727f24bb7dfc36ea4 | setup-gbrain | claude-code | skill | active | confirmed/confirmed (confirmed) | 38 | 14,974 | 0 | 0 次 | 55（Agent内归一） | 超重无refs |
| claude-code::i::f28d8e1e73aeeb14b1fa | autoplan | claude-code | skill | active | confirmed/confirmed (confirmed) | 38 | 16,769 | 0 | 0 次 | 55（Agent内归一） | 超重无refs |
| claude-code::i::084d2fd5b2e74de33966 | skillhub-upload | claude-code | skill | active | confirmed/confirmed (confirmed) | 37 | 1,767 | 0 | 0 次 | 40（Agent内归一） | — |
| claude-code::i::e43a7a0cfccadac5fca1 | finishing-a-development-branch | claude-code | skill | active | confirmed/confirmed (confirmed) | 37 | 1,035 | 0 | 0 次 | 38（Agent内归一） | — |
| claude-code::i::6a9dbe58810fbc27da32 | design-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 33 | 32,310 | 0 | 0 次 | 55（Agent内归一） | 超重无refs |
| claude-code::i::cbc4e50f756f40479b5b | ship | claude-code | skill | active | confirmed/confirmed (confirmed) | 33 | 19,096 | 0 | 0 次 | 55（Agent内归一） | 超重无refs |
| claude-code::i::e522a90ed7c1e42b19cf | receiving-code-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 33 | 1,446 | 0 | 0 次 | 38（Agent内归一） | — |
| claude-code::i::54b3070070b8402c1aa9 | lark-vc-agent | claude-code | skill | active | confirmed/confirmed (confirmed) | 31 | 57 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| claude-code::i::601461f7b08068743b8d | codex:gpt-5-4-prompting | claude-code | skill | active | confirmed/confirmed (confirmed) | 30 | 725 | 2,086 | 0 次 | 36（Agent内归一） | — |
| claude-code::i::8c94e81be3dcddba9e8b | lark-minutes | claude-code | skill | active | confirmed/confirmed (confirmed) | 30 | 57 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| claude-code::i::c1dd8cc45c362d59f99f | browse | claude-code | skill | active | confirmed/confirmed (confirmed) | 30 | 7,606 | 0 | 0 次 | 53（Agent内归一） | — |
| claude-code::i::e67cdbdf4561824d1ce5 | lark-vc | claude-code | skill | active | confirmed/confirmed (confirmed) | 30 | 57 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| claude-code::i::6b898f2b0ff3bc02c5a5 | using-git-worktrees | claude-code | skill | active | confirmed/confirmed (confirmed) | 29 | 1,303 | 0 | 0 次 | 37（Agent内归一） | — |
| claude-code::i::6c32340bd195683e9f07 | lark-note | claude-code | skill | active | confirmed/confirmed (confirmed) | 29 | 57 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| claude-code::i::2666157cb458297248d1 | using-superpowers | claude-code | skill | active | confirmed/confirmed (confirmed) | 25 | 1,212 | 1,333 | 9 次 | 27（Agent内归一） | — |
| claude-code::i::66231950afcb27ea108b | design-shotgun | claude-code | skill | active | confirmed/confirmed (confirmed) | 25 | 12,742 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| claude-code::i::085181f415c03afe8d54 | sync-gbrain | claude-code | skill | active | confirmed/confirmed (confirmed) | 24 | 13,418 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| claude-code::i::2d643a338c80029d615c | scrape | claude-code | skill | active | confirmed/confirmed (confirmed) | 23 | 6,534 | 0 | 0 次 | 50（Agent内归一） | — |
| claude-code::i::cb46a89674f011ab852a | skillify | claude-code | skill | active | confirmed/confirmed (confirmed) | 23 | 11,366 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| claude-code::i::e491a6eed92c064c3384 | ios-clean | claude-code | skill | active | confirmed/confirmed (confirmed) | 23 | 7,989 | 0 | 0 次 | 53（Agent内归一） | — |
| claude-code::i::777400ba6214edc348e6 | plan-tune | claude-code | skill | active | confirmed/confirmed (confirmed) | 22 | 14,341 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| claude-code::i::89b86c9b5f56cff593a9 | unfreeze | claude-code | skill | active | confirmed/confirmed (confirmed) | 20 | 341 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| claude-code::i::210a83c76555e1ee4758 | document-generate | claude-code | skill | active | confirmed/confirmed (confirmed) | 19 | 11,271 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| claude-code::i::6582ae5b3c949ddad11c | cso | claude-code | skill | active | confirmed/confirmed (confirmed) | 19 | 3,596 | 0 | 0 次 | 42（Agent内归一） | — |
| claude-code::i::9011755dd078e310cd02 | dispatching-parallel-agents | claude-code | skill | active | confirmed/confirmed (confirmed) | 19 | 1,421 | 0 | 0 次 | 36（Agent内归一） | — |
| claude-code::i::aee952707f6c2b6b6dc4 | ios-sync | claude-code | skill | active | confirmed/confirmed (confirmed) | 19 | 8,037 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| claude-code::i::1a1df599df84515e11b9 | setup-browser-cookies | claude-code | skill | active | confirmed/confirmed (confirmed) | 18 | 2,940 | 0 | 0 次 | 40（Agent内归一） | — |
| claude-code::i::7985bf478e3d38e1829d | design-html | claude-code | skill | active | confirmed/confirmed (confirmed) | 18 | 13,429 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::94112ddc37a3d452af14 | plan-design-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 18 | 18,744 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::08c0265bde1c0cb4cc79 | writing-plans | claude-code | skill | active | confirmed/confirmed (confirmed) | 17 | 1,359 | 0 | 0 次 | 36（Agent内归一） | — |
| claude-code::i::323bcbf1210d27ab0052 | requesting-code-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 17 | 658 | 0 | 0 次 | 34（Agent内归一） | — |
| claude-code::i::5dddef460ffeb587a9e3 | spec | claude-code | skill | active | confirmed/confirmed (confirmed) | 17 | 13,765 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::d6cf53aaadbaedb6f188 | executing-plans | claude-code | skill | active | confirmed/confirmed (confirmed) | 17 | 504 | 0 | 0 次 | 34（Agent内归一） | — |
| claude-code::i::facc1f3f743a1cd33559 | guard | claude-code | skill | active | confirmed/confirmed (confirmed) | 17 | 629 | 0 | 0 次 | 34（Agent内归一） | — |
| claude-code::i::08d9832c65eb38d09643 | freeze | claude-code | skill | active | confirmed/confirmed (confirmed) | 16 | 768 | 0 | 0 次 | 34（Agent内归一） | — |
| claude-code::i::b089cbfba897025dfbfb | systematic-debugging | claude-code | skill | active | confirmed/confirmed (confirmed) | 16 | 2,261 | 0 | 0 次 | 38（Agent内归一） | — |
| claude-code::i::df02a99135776de20b5c | writing-skills | claude-code | skill | active | confirmed/confirmed (confirmed) | 16 | 5,027 | 0 | 2 次 | 43（Agent内归一） | — |
| claude-code::i::e88747e38deb25335d79 | qa | claude-code | skill | active | confirmed/confirmed (confirmed) | 16 | 14,903 | 未确认 | 0 次 | — | — |
| claude-code::i::338efc23b7191816e619 | connect-chrome | claude-code | skill | active | confirmed/confirmed (confirmed) | 15 | 4,341 | 0 | 0 次 | 43（Agent内归一） | — |
| claude-code::i::7fade8747a54de58e6e8 | open-gstack-browser | claude-code | skill | active | confirmed/confirmed (confirmed) | 15 | 4,341 | 0 | 0 次 | 43（Agent内归一） | — |
| claude-code::i::b2cb8e58c13a2e0b253b | ios-design-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 15 | 8,180 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::4bd3133b934016955378 | codex:codex-cli-runtime | claude-code | skill | active | confirmed/confirmed (confirmed) | 14 | 717 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| claude-code::i::5834446457f0dc68a164 | make-pdf | claude-code | skill | active | confirmed/confirmed (confirmed) | 14 | 4,921 | 0 | 0 次 | 44（Agent内归一） | — |
| claude-code::i::7d603c7fd3562c64028a | context-restore | claude-code | skill | active | confirmed/confirmed (confirmed) | 14 | 8,837 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::c5cf8013ef7e54f47336 | codex | claude-code | skill | active | confirmed/confirmed (confirmed) | 14 | 14,745 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::d81d111ae032b1f1b72b | lark-attendance | claude-code | skill | active | confirmed/confirmed (confirmed) | 14 | 386 | 0 | 0 次 | 33（Agent内归一） | 骨架 |
| claude-code::i::fab75ced9aaab6252e80 | ios-qa | claude-code | skill | active | confirmed/confirmed (confirmed) | 14 | 10,517 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::9e4f7e166f5fa3586ee1 | landing-report | claude-code | skill | active | confirmed/confirmed (confirmed) | 13 | 8,580 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::9e8894ca9be2c0ab2f21 | pair-agent | claude-code | skill | active | confirmed/confirmed (confirmed) | 13 | 10,854 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::dc569680912fdca983f6 | test-driven-development | claude-code | skill | active | confirmed/confirmed (confirmed) | 13 | 2,383 | 0 | 0 次 | 38（Agent内归一） | — |
| claude-code::i::245d8642e4a5e4d3876f | investigate | claude-code | skill | active | confirmed/confirmed (confirmed) | 12 | 10,917 | 0 | 2 次 | 50（Agent内归一） | 超重无refs |
| claude-code::i::2b1fbc75fa341fc10d13 | gstack | claude-code | skill | active | confirmed/confirmed (confirmed) | 12 | 3,540 | 0 | 0 次 | 41（Agent内归一） | — |
| claude-code::i::54c88ffff0fb8c348182 | subagent-driven-development | claude-code | skill | active | confirmed/confirmed (confirmed) | 12 | 2,670 | 0 | 0 次 | 38（Agent内归一） | — |
| claude-code::i::921f659ff2c7e607e8c9 | codex:codex-result-handling | claude-code | skill | active | confirmed/confirmed (confirmed) | 12 | 337 | 0 | 0 次 | 32（Agent内归一） | 骨架 |
| claude-code::i::a04e9d8d81d8ccf00e62 | _gstack-command | claude-code | skill | active | confirmed/confirmed (confirmed) | 12 | 3,540 | 0 | 0 次 | 41（Agent内归一） | — |
| claude-code::i::a1849366a2e4b4b6060b | plan-ceo-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 12 | 19,054 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::c623287396c8ff529609 | benchmark-models | claude-code | skill | active | confirmed/confirmed (confirmed) | 12 | 3,529 | 0 | 0 次 | 40（Agent内归一） | — |
| claude-code::i::0cb3507e135a1e35c057 | careful | claude-code | skill | active | confirmed/confirmed (confirmed) | 11 | 843 | 0 | 0 次 | 34（Agent内归一） | — |
| claude-code::i::4fe44eaf69924463d3d1 | ios-fix | claude-code | skill | active | confirmed/confirmed (confirmed) | 11 | 8,031 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::caa354554922cc3a9d1e | office-hours | claude-code | skill | active | confirmed/confirmed (confirmed) | 11 | 20,455 | 0 | 1 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::d975d6c3b4844a24344d | canary | claude-code | skill | active | confirmed/confirmed (confirmed) | 11 | 13,074 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| claude-code::i::180c092ad2d8ff2b3464 | remotion-best-practices | claude-code | skill | active | confirmed/confirmed (confirmed) | 10 | 847 | 0 | 0 次 | 33（Agent内归一） | 骨架 |
| claude-code::i::23271c2b9119e9e69421 | document-release | claude-code | skill | active | confirmed/confirmed (confirmed) | 10 | 9,765 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::4dc5ce61a65c01583f11 | review | claude-code | skill | active | confirmed/confirmed (confirmed) | 10 | 14,811 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::578e57827e534470c67a | plan-devex-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 10 | 16,816 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::73bba65c8002f235725a | setup-deploy | claude-code | skill | active | confirmed/confirmed (confirmed) | 10 | 10,665 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::c05114f49da006befc9c | plan-eng-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 10 | 13,719 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::1a82026369bc17a6870f | qa-only | claude-code | skill | active | confirmed/confirmed (confirmed) | 9 | 16,106 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::3bc43cc39832df73a44f | devex-review | claude-code | skill | active | confirmed/confirmed (confirmed) | 9 | 19,154 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::e534d036728ca40acf1f | land-and-deploy | claude-code | skill | active | confirmed/confirmed (confirmed) | 9 | 17,997 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::123d384b8d3cff1ddef5 | gstack-upgrade | claude-code | skill | active | confirmed/confirmed (confirmed) | 8 | 4,833 | 0 | 0 次 | 43（Agent内归一） | — |
| claude-code::i::3da65e284231bcdedcee | benchmark | claude-code | skill | active | confirmed/confirmed (confirmed) | 8 | 7,271 | 0 | 0 次 | 49（Agent内归一） | — |
| claude-code::i::4bd0d3516d14a997eac3 | retro | claude-code | skill | active | confirmed/confirmed (confirmed) | 8 | 18,184 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::897d01f0629036e00ce9 | health | claude-code | skill | active | confirmed/confirmed (confirmed) | 8 | 11,297 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::fc8b87dcfc3dc7c7119d | context-save | claude-code | skill | active | confirmed/confirmed (confirmed) | 8 | 9,434 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::3feea9fe5372515d863e | learn | claude-code | skill | active | confirmed/confirmed (confirmed) | 5 | 8,609 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| claude-code::i::f0cbef4e2607bc7901f7 | amazon-listing-doctor | claude-code | skill | active | confirmed/confirmed (confirmed) | 0 | 4,594 | 20,818 | 0 次 | 41（Agent内归一） | — |
| codex::i::83cebfba383d8625d3d9 | skill-production-factory | codex | skill | active | confirmed/confirmed (confirmed) | 362 | 3,068 | 6,172 | 0 次 | 88（Agent内归一） | — |
| codex::i::5555e8a6c75ffa1c69d9 | lark-apps | codex | skill | active | confirmed/confirmed (confirmed) | 342 | 6,728 | 45,859 | 5 次 | 89（Agent内归一） | — |
| codex::i::05599777bf13b9a775df | review-analyzer-skill | codex | skill | active | confirmed/confirmed (confirmed) | 334 | 1,876 | 3,999 | 0 次 | 81（Agent内归一） | — |
| codex::i::550c77809b22c25acf0c | lark-sheets | codex | skill | active | confirmed/confirmed (confirmed) | 292 | 7,837 | 116,513 | 0 次 | 90（Agent内归一） | — |
| codex::i::34cec9b80e07de3d93d9 | zsxq | codex | skill | active | confirmed/confirmed (confirmed) | 290 | 4,318 | 55,859 | 0 次 | 81（Agent内归一） | — |
| codex::i::50854c4b74114bae41be | buluu-weekly-digest | codex | skill | active | confirmed/confirmed (confirmed) | 275 | 2,241 | 15,781 | 0 次 | 74（Agent内归一） | — |
| codex::i::f02267235a6c780ef53f | using-coze-cli | codex | skill | active | confirmed/confirmed (confirmed) | 227 | 7,613 | 0 | 0 次 | 80（Agent内归一） | — |
| codex::i::cc9246095644b8062a8a | seedance-video-script | codex | skill | active | confirmed/confirmed (confirmed) | 218 | 2,361 | 5,860 | 1 次 | 65（Agent内归一） | — |
| codex::i::055e14f0bcb6e4af7dab | n8n-goal-loop | codex | skill | active | confirmed/confirmed (confirmed) | 206 | 1,296 | 19,993 | 0 次 | 62（Agent内归一） | — |
| codex::i::4b4d172d6dbc3346edfd | n8n-goal-loop | codex | skill | active | confirmed/confirmed (confirmed) | 206 | 1,296 | 19,993 | 0 次 | 62（Agent内归一） | — |
| codex::i::0cd8927a74e04bf0ff0d | lark-drive | codex | skill | active | confirmed/confirmed (confirmed) | 204 | 6,472 | 124,750 | 0 次 | 74（Agent内归一） | — |
| codex::i::d7f8c68c84ebed4e397a | buluu-daily-brief | codex | skill | active | confirmed/confirmed (confirmed) | 203 | 2,377 | 11,225 | 0 次 | 64（Agent内归一） | — |
| codex::i::e7e9de944c92e5b26910 | neat-freak | codex | skill | active | confirmed/confirmed (confirmed) | 197 | 3,778 | 2,771 | 0 次 | 67（Agent内归一） | — |
| codex::i::59cb668109e278d248bf | office-hours | codex | skill | active | confirmed/confirmed (confirmed) | 165 | 24,498 | 0 | 0 次 | 73（Agent内归一） | 超重无refs |
| codex::i::e7bd73617e8e229d4cd3 | lark-wiki | codex | skill | active | confirmed/confirmed (confirmed) | 164 | 3,222 | 16,729 | 0 次 | 61（Agent内归一） | — |
| codex::i::454fac2ad68e617ac9bc | design-html | codex | skill | active | confirmed/confirmed (confirmed) | 163 | 13,840 | 0 | 0 次 | 73（Agent内归一） | 超重无refs |
| codex::i::a9eea0f898ad3712270d | qa | codex | skill | active | confirmed/confirmed (confirmed) | 158 | 16,398 | 812 | 0 次 | 72（Agent内归一） | — |
| codex::i::4352f1cbfb644f6259e5 | plan-devex-review | codex | skill | active | confirmed/confirmed (confirmed) | 151 | 22,902 | 0 | 0 次 | 71（Agent内归一） | 超重无refs |
| codex::i::6ba8dcd7f0a1e20c4700 | devex-review | codex | skill | active | confirmed/confirmed (confirmed) | 151 | 14,245 | 0 | 0 次 | 71（Agent内归一） | 超重无refs |
| codex::i::f4eb4b80ead3008f047c | lark-slides | codex | skill | active | confirmed/confirmed (confirmed) | 151 | 7,598 | 320,181 | 2 次 | 68（Agent内归一） | — |
| codex::i::4ba5c7ee9c8121b48f13 | cso | codex | skill | active | confirmed/confirmed (confirmed) | 150 | 16,670 | 0 | 0 次 | 71（Agent内归一） | 超重无refs |
| codex::i::026fb41aab3011f0711f | autoplan | codex | skill | active | confirmed/confirmed (confirmed) | 149 | 18,478 | 0 | 0 次 | 71（Agent内归一） | 超重无refs |
| codex::i::548b77aab37056328a41 | ai-intel-hub | codex | skill | active | confirmed/confirmed (confirmed) | 147 | 6,687 | 0 | 0 次 | 67（Agent内归一） | — |
| codex::i::120aad72f8babd0cb553 | plan-ceo-review | codex | skill | active | confirmed/confirmed (confirmed) | 138 | 26,597 | 0 | 0 次 | 69（Agent内归一） | 超重无refs |
| codex::i::20fd7e867d4a9ccd63e1 | lark-im | codex | skill | active | confirmed/confirmed (confirmed) | 136 | 6,258 | 80,149 | 0 次 | 64（Agent内归一） | — |
| codex::i::8223ce91881965a102c9 | pair-agent | codex | skill | active | confirmed/confirmed (confirmed) | 136 | 9,992 | 0 | 0 次 | 69（Agent内归一） | 超重无refs |
| codex::i::8801a12fd24c95fed456 | blue-video-script | codex | skill | active | confirmed/confirmed (confirmed) | 133 | 2,079 | 40,856 | 0 次 | 54（Agent内归一） | — |
| codex::i::ded6bc52f4dfae8a4a2e | agentkey | codex | skill | active | confirmed/confirmed (confirmed) | 133 | 1,766 | 4,277 | 1 次 | 52（Agent内归一） | — |
| codex::i::bbd8b7836f67b80e09fa | lark-base | codex | skill | active | confirmed/confirmed (confirmed) | 127 | 6,295 | 103,172 | 0 次 | 63（Agent内归一） | — |
| codex::i::839dedfae1313a5b7d59 | n8n-code-javascript | codex | skill | active | confirmed/confirmed (confirmed) | 123 | 4,638 | 0 | 0 次 | 59（Agent内归一） | — |
| codex::i::e8a581b8d6689d0c5f45 | design-review | codex | skill | active | confirmed/confirmed (confirmed) | 122 | 19,539 | 0 | 5 次 | 62（Agent内归一） | 超重无refs |
| codex::i::7fb85b87323aed21673e | lark-task | codex | skill | active | confirmed/confirmed (confirmed) | 121 | 3,513 | 7,932 | 1 次 | 54（Agent内归一） | — |
| codex::i::aed5e8b0c7a0108b4976 | n8n-mcp-tools-expert | codex | skill | active | confirmed/confirmed (confirmed) | 121 | 7,317 | 0 | 0 次 | 65（Agent内归一） | — |
| codex::i::fcabaf5a8c7a23ebd7ef | takumi | codex | skill | active | confirmed/confirmed (confirmed) | 121 | 1,926 | 632 | 0 次 | 52（Agent内归一） | — |
| codex::i::55312bc83197f9d21d6f | lark-doc | codex | skill | active | confirmed/confirmed (confirmed) | 120 | 951 | 49,452 | 0 次 | 49（Agent内归一） | — |
| codex::i::c40165153881125bd21f | ai-intel-hub | codex | skill | active | confirmed/confirmed (confirmed) | 119 | 2,725 | 0 | 0 次 | 53（Agent内归一） | — |
| codex::i::1437e1a518ab0cbfeffc | codex | codex | skill | active | confirmed/confirmed (confirmed) | 117 | 14,164 | 0 | 0 次 | 66（Agent内归一） | 超重无refs |
| codex::i::31b7580a3044b6e23387 | browse | codex | skill | active | confirmed/confirmed (confirmed) | 117 | 8,947 | 0 | 0 次 | 66（Agent内归一） | 超重无refs |
| codex::i::2abd221f1f4185440941 | logo-generator | codex | skill | active | confirmed/confirmed (confirmed) | 116 | 1,618 | 12,799 | 0 次 | 50（Agent内归一） | — |
| codex::i::e12ba091df86d9dd79f1 | lark-contact | codex | skill | active | confirmed/confirmed (confirmed) | 116 | 926 | 2,570 | 0 次 | 48（Agent内归一） | — |
| codex::i::f080e99caa155f5738ea | logo-generator | codex | skill | active | confirmed/confirmed (confirmed) | 116 | 1,618 | 12,799 | 0 次 | 50（Agent内归一） | — |
| codex::i::4b2117f63c2701150b3d | lark-event | codex | skill | active | confirmed/confirmed (confirmed) | 114 | 2,670 | 7,133 | 0 次 | 52（Agent内归一） | — |
| codex::i::960a43fd64e2bfcef6f0 | kami | codex | skill | active | confirmed/confirmed (confirmed) | 113 | 5,905 | 34,306 | 0 次 | 60（Agent内归一） | — |
| codex::i::a1bd48d5e27844991ff5 | kami | codex | skill | active | confirmed/confirmed (confirmed) | 113 | 5,902 | 34,306 | 0 次 | 60（Agent内归一） | — |
| codex::i::ecbe735eb23be3ff6856 | lark-meeting | codex | skill | active | confirmed/confirmed (confirmed) | 113 | 3,058 | 32,719 | 0 次 | 53（Agent内归一） | — |
| codex::i::6920e92b23e93510073d | plan-eng-review | codex | skill | active | confirmed/confirmed (confirmed) | 112 | 20,230 | 0 | 0 次 | 65（Agent内归一） | 超重无refs |
| codex::i::8cb1723662c3e99af80a | imagegen | codex | skill | active | confirmed/confirmed (confirmed) | 110 | 未确认 | 未确认 | 1 次 | — | — |
| codex::i::05ced05cc20320b67122 | design-consultation | codex | skill | active | confirmed/confirmed (confirmed) | 109 | 16,419 | 0 | 0 次 | 65（Agent内归一） | 超重无refs |
| codex::i::2fa955214243b5be477a | n8n-workflow-patterns | codex | skill | active | confirmed/confirmed (confirmed) | 109 | 3,633 | 0 | 0 次 | 54（Agent内归一） | — |
| codex::i::c233ecd50cd50050f225 | investigate | codex | skill | active | confirmed/confirmed (confirmed) | 109 | 9,707 | 0 | 0 次 | 65（Agent内归一） | 超重无refs |
| codex::i::25b56eec197334a045e6 | qa-only | codex | skill | active | confirmed/confirmed (confirmed) | 108 | 12,358 | 0 | 0 次 | 65（Agent内归一） | 超重无refs |
| codex::i::c7a856eea1d47446c0d7 | openai-docs | codex | skill | active | confirmed/confirmed (confirmed) | 108 | 未确认 | 未确认 | 0 次 | — | — |
| codex::i::dd72b20caa1a524cb60a | guizang-ppt-skill | codex | skill | active | confirmed/confirmed (confirmed) | 107 | 4,945 | 22,348 | 0 次 | 57（Agent内归一） | — |
| codex::i::ddee191ece9b98c3b176 | guizang-ppt-skill | codex | skill | active | confirmed/confirmed (confirmed) | 107 | 4,945 | 22,348 | 0 次 | 57（Agent内归一） | — |
| codex::i::43af6ac3d0c7c3f228ac | ship | codex | skill | active | confirmed/confirmed (confirmed) | 103 | 32,702 | 0 | 0 次 | 64（Agent内归一） | 超重无refs |
| codex::i::304b0f0f14d8c519d9e4 | open-gstack-browser | codex | skill | active | confirmed/confirmed (confirmed) | 102 | 9,953 | 0 | 0 次 | 64（Agent内归一） | 超重无refs |
| codex::i::bd54c98d5407dac42df0 | n8n-code-python | codex | skill | active | confirmed/confirmed (confirmed) | 102 | 4,707 | 0 | 0 次 | 56（Agent内归一） | — |
| codex::i::01e5632e2ccc8055dea4 | checkpoint | codex | skill | active | confirmed/confirmed (confirmed) | 100 | 9,513 | 0 | 0 次 | 64（Agent内归一） | 超重无refs |
| codex::i::161924cc9bfd2f11e03a | setup-deploy | codex | skill | active | confirmed/confirmed (confirmed) | 99 | 9,259 | 0 | 0 次 | 64（Agent内归一） | 超重无refs |
| codex::i::cceabf0b27b740f7ed5d | lark-whiteboard | codex | skill | active | confirmed/confirmed (confirmed) | 99 | 734 | 3,975 | 0 次 | 46（Agent内归一） | — |
| codex::i::22e8cac93718fc437090 | plan-design-review | codex | skill | active | confirmed/confirmed (confirmed) | 98 | 21,350 | 0 | 0 次 | 64（Agent内归一） | 超重无refs |
| codex::i::27451207cc61e39f4603 | benchmark | codex | skill | active | confirmed/confirmed (confirmed) | 92 | 7,811 | 0 | 0 次 | 62（Agent内归一） | — |
| codex::i::2e675d2044138cf90783 | any2card | codex | skill | active | confirmed/confirmed (confirmed) | 92 | 3,855 | 4,107 | 0 次 | 52（Agent内归一） | — |
| codex::i::6da345ac180e27ab384b | document-release | codex | skill | active | confirmed/confirmed (confirmed) | 92 | 11,147 | 0 | 0 次 | 63（Agent内归一） | 超重无refs |
| codex::i::a922cc55dd41575f38d6 | any2card | codex | skill | active | confirmed/confirmed (confirmed) | 92 | 3,855 | 4,107 | 0 次 | 52（Agent内归一） | — |
| codex::i::e05a79df77978db206ff | guizang-social-card-skill | codex | skill | active | confirmed/confirmed (confirmed) | 91 | 5,996 | 39,528 | 0 次 | 58（Agent内归一） | — |
| codex::i::4872cc10db1023dfb88b | lark-calendar | codex | skill | active | confirmed/confirmed (confirmed) | 88 | 4,871 | 19,206 | 1 次 | 53（Agent内归一） | — |
| codex::i::23623e0b2f03da14cb82 | guard | codex | skill | active | confirmed/confirmed (confirmed) | 86 | 522 | 0 | 0 次 | 43（Agent内归一） | — |
| codex::i::d0b3c8d466c0e2735c1b | n8n-expression-syntax | codex | skill | active | confirmed/confirmed (confirmed) | 86 | 2,608 | 0 | 0 次 | 48（Agent内归一） | — |
| codex::i::ed6daf413bae00463f4e | lark-approval | codex | skill | active | confirmed/confirmed (confirmed) | 86 | 1,795 | 29,396 | 0 次 | 46（Agent内归一） | — |
| codex::i::d3267222654b58cfde1d | lark-markdown | codex | skill | active | confirmed/confirmed (confirmed) | 85 | 1,230 | 6,000 | 1 次 | 44（Agent内归一） | — |
| codex::i::da75408d44b82d18b200 | design-shotgun | codex | skill | active | confirmed/confirmed (confirmed) | 85 | 11,772 | 0 | 0 次 | 62（Agent内归一） | 超重无refs |
| codex::i::3a56a60131b431adc589 | n8n-validation-expert | codex | skill | active | confirmed/confirmed (confirmed) | 84 | 4,363 | 0 | 0 次 | 53（Agent内归一） | — |
| codex::i::448f69397e454ebe0841 | careful | codex | skill | active | confirmed/confirmed (confirmed) | 84 | 503 | 0 | 0 次 | 43（Agent内归一） | 骨架 |
| codex::i::1f50c2fac1da197bee1a | lark-mail | codex | skill | active | confirmed/confirmed (confirmed) | 82 | 6,792 | 56,442 | 1 次 | 57（Agent内归一） | — |
| codex::i::974d25d9da774a8aedf6 | lark-okr | codex | skill | active | confirmed/confirmed (confirmed) | 82 | 2,845 | 37,177 | 0 次 | 48（Agent内归一） | — |
| codex::i::cfc053403254413c456a | plugin-creator | codex | skill | active | confirmed/confirmed (confirmed) | 82 | 未确认 | 未确认 | 0 次 | — | — |
| codex::i::2b1f05028eb2e6e6bb6c | qiaomu-goal-meta-skill | codex | skill | active | confirmed/confirmed (confirmed) | 81 | 1,525 | 5,544 | 0 次 | 45（Agent内归一） | — |
| codex::i::36d945e35ad1ea31ee0f | gstack | codex | skill | active | confirmed/confirmed (confirmed) | 81 | 10,064 | 0 | 0 次 | 61（Agent内归一） | 超重无refs |
| codex::i::c218a30ad8c0e5bb23ad | review | codex | skill | active | confirmed/confirmed (confirmed) | 79 | 19,095 | 0 | 0 次 | 61（Agent内归一） | 超重无refs |
| codex::i::92be9850ff657a3e13d5 | n8n-node-configuration | codex | skill | active | confirmed/confirmed (confirmed) | 77 | 4,494 | 0 | 0 次 | 52（Agent内归一） | — |
| codex::i::1ada1130a34d1f18ce58 | template-creator:template-creator | codex | skill | active | confirmed/confirmed (confirmed) | 76 | 1,322 | 0 | 0 次 | 44（Agent内归一） | — |
| codex::i::4a3996d8494a255b1614 | canary | codex | skill | active | confirmed/confirmed (confirmed) | 76 | 10,138 | 0 | 0 次 | 60（Agent内归一） | 超重无refs |
| codex::i::8d96fbcfa2e237c0ebaf | e-commerce-find-skills | codex | skill | active | confirmed/confirmed (confirmed) | 75 | 573 | 0 | 0 次 | 42（Agent内归一） | — |
| codex::i::b9bfc0bfe69d913c0ea7 | health | codex | skill | active | confirmed/confirmed (confirmed) | 75 | 10,116 | 0 | 0 次 | 60（Agent内归一） | 超重无refs |
| codex::i::2b98f94177169e9a482d | retro | codex | skill | active | confirmed/confirmed (confirmed) | 74 | 18,008 | 0 | 0 次 | 60（Agent内归一） | 超重无refs |
| codex::i::3e1be6e42c9e9f12cb02 | frontend-design | codex | skill | active | confirmed/confirmed (confirmed) | 74 | 767 | 0 | 8 次 | 34（Agent内归一） | 骨架 |
| codex::i::c8abe0cf0d3bd9834d6c | freeze | codex | skill | active | confirmed/confirmed (confirmed) | 74 | 556 | 0 | 0 次 | 42（Agent内归一） | — |
| codex::i::086ec7654d4247f34972 | gstack-upgrade | codex | skill | active | confirmed/confirmed (confirmed) | 73 | 2,915 | 0 | 0 次 | 47（Agent内归一） | — |
| codex::i::c3241313c54713a14eb2 | ppt-master | codex | skill | active | confirmed/confirmed (confirmed) | 73 | 6,109 | 36,756 | 0 次 | 55（Agent内归一） | — |
| codex::i::620e2d66cac0f4913ef6 | drawio | codex | skill | active | confirmed/confirmed (confirmed) | 72 | 1,979 | 0 | 3 次 | 42（Agent内归一） | — |
| codex::i::fe3f0bca9413c93d8627 | drawio | codex | skill | active | confirmed/confirmed (confirmed) | 72 | 1,979 | 0 | 1 次 | 44（Agent内归一） | — |
| codex::i::af89768a1e1523d21372 | learn | codex | skill | active | confirmed/confirmed (confirmed) | 71 | 8,781 | 0 | 0 次 | 60（Agent内归一） | 超重无refs |
| codex::i::5e7b28db3c3976836bd5 | skill-publish | codex | skill | active | confirmed/confirmed (confirmed) | 70 | 1,390 | 7,922 | 23 次 | 20（Agent内归一） | — |
| codex::i::faf73a528d390d003745 | amazon-asin-competitor-materials | codex | skill | active | confirmed/confirmed (confirmed) | 70 | 761 | 485 | 0 次 | 42（Agent内归一） | — |
| codex::i::92e625c62422728b1a4e | lark-openapi-explorer | codex | skill | active | confirmed/confirmed (confirmed) | 69 | 1,379 | 0 | 0 次 | 43（Agent内归一） | — |
| codex::i::ad8913e0520ffdb91a92 | documents:documents | codex | skill | active | confirmed/confirmed (confirmed) | 69 | 8,502 | 8,079 | 0 次 | 60（Agent内归一） | — |
| codex::i::37fc65da8f6e81df5f4e | ecommerce-competitor-analyzer | codex | skill | active | confirmed/confirmed (confirmed) | 68 | 1,560 | 1,978 | 0 次 | 43（Agent内归一） | — |
| codex::i::0e9f1c76146e3ee5d32b | land-and-deploy | codex | skill | active | confirmed/confirmed (confirmed) | 66 | 20,145 | 0 | 0 次 | 59（Agent内归一） | 超重无refs |
| codex::i::c9ded01e2bab0ae4c65e | wechat-crawler | codex | skill | active | confirmed/confirmed (confirmed) | 65 | 824 | 483 | 0 次 | 41（Agent内归一） | — |
| codex::i::d3b79b22beffa309cdcd | find-skills | codex | skill | active | confirmed/confirmed (confirmed) | 63 | 1,047 | 0 | 0 次 | 41（Agent内归一） | — |
| codex::i::35d9d4660520b0220a72 | skill-creator | codex | skill | active | confirmed/confirmed (confirmed) | 60 | 8,327 | 19,278 | 9 次 | 49（Agent内归一） | — |
| codex::i::8df136a3dd81a3b904cb | setup-browser-cookies | codex | skill | active | confirmed/confirmed (confirmed) | 60 | 6,060 | 0 | 0 次 | 53（Agent内归一） | — |
| codex::i::ddf69fbf8d66919459b1 | skill-creator | codex | skill | active | confirmed/confirmed (confirmed) | 60 | 4,495 | 7,524 | 0 次 | 50（Agent内归一） | — |
| codex::i::6e4684339710b6be5823 | unfreeze | codex | skill | active | confirmed/confirmed (confirmed) | 57 | 289 | 0 | 0 次 | 39（Agent内归一） | 骨架 |
| codex::i::9e5594815381bc9873eb | browser:control-in-app-browser | codex | skill | active | confirmed/confirmed (confirmed) | 56 | 2,054 | 0 | 0 次 | 43（Agent内归一） | — |
| codex::i::a977d6b8749425fe736a | codex-imagegen | codex | skill | active | confirmed/confirmed (confirmed) | 56 | 1,166 | 0 | 0 次 | 41（Agent内归一） | — |
| codex::i::8a317a7af624c7f0a793 | wechat-crawler | codex | skill | active | confirmed/confirmed (confirmed) | 55 | 424 | 483 | 0 次 | 39（Agent内归一） | — |
| codex::i::4a60b891265f651192f1 | gstack-openclaw-retro | codex | skill | active | confirmed/confirmed (confirmed) | 53 | 2,422 | 0 | 0 次 | 43（Agent内归一） | — |
| codex::i::d5195d1a9d39730979a9 | gstack-openclaw-retro | codex | skill | active | confirmed/confirmed (confirmed) | 53 | 2,408 | 0 | 0 次 | 43（Agent内归一） | — |
| codex::i::7b3df220d5b5922549d1 | spreadsheets:excel-live-control | codex | skill | active | confirmed/confirmed (confirmed) | 51 | 4,702 | 0 | 0 次 | 49（Agent内归一） | — |
| codex::i::debff0f7ab8d28e84106 | superpowers:brainstorming | codex | skill | active | confirmed/confirmed (confirmed) | 51 | 2,428 | 0 | 9 次 | 34（Agent内归一） | — |
| codex::i::2432e7fc1650736cd96b | skill-installer | codex | skill | active | confirmed/confirmed (confirmed) | 50 | 未确认 | 未确认 | 0 次 | — | — |
| codex::i::f25cb3e4668636748c49 | spreadsheets:Spreadsheets | codex | skill | active | confirmed/confirmed (confirmed) | 48 | 3,149 | 0 | 0 次 | 45（Agent内归一） | — |
| codex::i::c7914fc684c87dd6fb0a | lark-workflow-meeting-summary | codex | skill | active | confirmed/confirmed (confirmed) | 47 | 1,976 | 0 | 0 次 | 41（Agent内归一） | — |
| codex::i::924170dc8195c2630f3b | diagram | codex | skill | active | confirmed/confirmed (confirmed) | 46 | 4,083 | 0 | 0 次 | 47（Agent内归一） | — |
| codex::i::c236e925ed8dc790aa55 | lark-shared | codex | skill | active | confirmed/confirmed (confirmed) | 44 | 1,088 | 3,582 | 7 次 | 32（Agent内归一） | — |
| codex::i::fb5d28c4dfbffd67af83 | lark-workflow-standup-report | codex | skill | active | confirmed/confirmed (confirmed) | 44 | 1,355 | 0 | 0 次 | 39（Agent内归一） | — |
| codex::i::9d57aa072a93aa3c9608 | agently-mail | codex | skill | active | confirmed/confirmed (confirmed) | 43 | 2,979 | 0 | 0 次 | 43（Agent内归一） | — |
| codex::i::79043ca6d2053a4f16f9 | visualize:visualize | codex | skill | active | confirmed/confirmed (confirmed) | 42 | 4,208 | 0 | 0 次 | 46（Agent内归一） | — |
| codex::i::f89ef7178755f12b9d62 | pdf:pdf | codex | skill | active | confirmed/confirmed (confirmed) | 42 | 565 | 0 | 1 次 | 36（Agent内归一） | — |
| codex::i::9fea5c1dde208a469527 | design-consultation | codex | skill | active | confirmed/confirmed (confirmed) | 41 | 17,236 | 0 | 0 次 | 56（Agent内归一） | 超重无refs |
| codex::i::a41771d59104f848b308 | lark-skill-maker | codex | skill | active | confirmed/confirmed (confirmed) | 40 | 660 | 0 | 0 次 | 37（Agent内归一） | — |
| codex::i::ebfb62d7844ee86dedc3 | web-design-guidelines | codex | skill | active | confirmed/confirmed (confirmed) | 39 | 191 | 0 | 0 次 | 36（Agent内归一） | 骨架 |
| codex::i::5ee28868ee065ca95f8a | gstack-openclaw-investigate | codex | skill | active | confirmed/confirmed (confirmed) | 38 | 1,175 | 0 | 0 次 | 38（Agent内归一） | — |
| codex::i::705e0225a2900c4e06e8 | gstack-openclaw-ceo-review | codex | skill | active | confirmed/confirmed (confirmed) | 38 | 2,343 | 0 | 0 次 | 41（Agent内归一） | — |
| codex::i::db293b34d54f5f5485d7 | superpowers:verification-before-completion | codex | skill | active | confirmed/confirmed (confirmed) | 38 | 925 | 0 | 8 次 | 30（Agent内归一） | — |
| codex::i::fd83bfcea6c3cc8054f6 | setup-gbrain | codex | skill | active | confirmed/confirmed (confirmed) | 38 | 14,974 | 0 | 0 次 | 55（Agent内归一） | 超重无refs |
| codex::i::fe05c874d37e9345a017 | autoplan | codex | skill | active | confirmed/confirmed (confirmed) | 38 | 16,769 | 0 | 0 次 | 55（Agent内归一） | 超重无refs |
| codex::i::01de9914ed139335532b | superpowers:finishing-a-development-branch | codex | skill | active | confirmed/confirmed (confirmed) | 37 | 1,035 | 0 | 2 次 | 36（Agent内归一） | — |
| codex::i::2b560f06c1c9ab68d3f5 | skillhub-upload | codex | skill | active | confirmed/confirmed (confirmed) | 37 | 1,767 | 0 | 0 次 | 40（Agent内归一） | — |
| codex::i::cb63d7e615dd0ff70084 | chrome:control-chrome | codex | skill | active | confirmed/confirmed (confirmed) | 36 | 2,054 | 0 | 0 次 | 40（Agent内归一） | — |
| codex::i::4f375c7a273738eab668 | gstack-openclaw-office-hours | codex | skill | active | confirmed/confirmed (confirmed) | 34 | 3,845 | 0 | 0 次 | 44（Agent内归一） | — |
| codex::i::2f14b7e1a8a70486887f | ship | codex | skill | active | confirmed/confirmed (confirmed) | 33 | 19,096 | 0 | 0 次 | 55（Agent内归一） | 超重无refs |
| codex::i::ec078b73f7d10a3f09ef | superpowers:receiving-code-review | codex | skill | active | confirmed/confirmed (confirmed) | 33 | 1,446 | 0 | 4 次 | 34（Agent内归一） | — |
| codex::i::edfd86c84f2fbde3e940 | design-review | codex | skill | active | confirmed/confirmed (confirmed) | 33 | 32,310 | 0 | 1 次 | 54（Agent内归一） | 超重无refs |
| codex::i::062084d2c66c0c28019f | lark-vc-agent | codex | skill | active | confirmed/confirmed (confirmed) | 31 | 57 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| codex::i::007ff156d9f0af5de136 | codex:gpt-5-4-prompting | codex | skill | active | confirmed/confirmed (confirmed) | 30 | 725 | 2,086 | 0 次 | 36（Agent内归一） | — |
| codex::i::32b37cedde71b3a40041 | browse | codex | skill | active | confirmed/confirmed (confirmed) | 30 | 7,606 | 0 | 2 次 | 51（Agent内归一） | — |
| codex::i::4d97b623294b8a22e002 | lark-minutes | codex | skill | active | confirmed/confirmed (confirmed) | 30 | 57 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| codex::i::8c77392e5ccc6a24c036 | lark-vc | codex | skill | active | confirmed/confirmed (confirmed) | 30 | 57 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| codex::i::2f387abfcf86657be61f | superpowers:using-git-worktrees | codex | skill | active | confirmed/confirmed (confirmed) | 29 | 1,303 | 0 | 0 次 | 37（Agent内归一） | — |
| codex::i::88b93f5e938f2ad177e0 | lark-note | codex | skill | active | confirmed/confirmed (confirmed) | 29 | 57 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| codex::i::71954d96e29e5d16e9cc | record-and-replay:record-and-replay | codex | skill | active | confirmed/confirmed (confirmed) | 27 | 953 | 0 | 1 次 | 35（Agent内归一） | 骨架 |
| codex::i::1b1de97b78620ce845e1 | design-shotgun | codex | skill | active | confirmed/confirmed (confirmed) | 25 | 12,742 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| codex::i::d21040985247adc2a138 | superpowers:using-superpowers | codex | skill | active | confirmed/confirmed (confirmed) | 25 | 1,212 | 1,333 | 1 次 | 35（Agent内归一） | — |
| codex::i::905e6a10b7bab6bbb9a6 | playwright-trace | codex | skill | active | confirmed/confirmed (confirmed) | 24 | 1,042 | 0 | 0 次 | 36（Agent内归一） | — |
| codex::i::94dbdb3c03719094d53f | sync-gbrain | codex | skill | active | confirmed/confirmed (confirmed) | 24 | 13,418 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| codex::i::9eb849e3f036d2f2195d | playwright-trace | codex | skill | active | confirmed/confirmed (confirmed) | 24 | 1,042 | 0 | 0 次 | 36（Agent内归一） | — |
| codex::i::8a880abbd584e2f58989 | skillify | codex | skill | active | confirmed/confirmed (confirmed) | 23 | 11,366 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| codex::i::cf4b723428b4606703db | ios-clean | codex | skill | active | confirmed/confirmed (confirmed) | 23 | 7,989 | 0 | 0 次 | 53（Agent内归一） | — |
| codex::i::fff9aeb2a3202eb2a2eb | scrape | codex | skill | active | confirmed/confirmed (confirmed) | 23 | 6,534 | 0 | 0 次 | 50（Agent内归一） | — |
| codex::i::00672f1c06dc667e7b1d | plan-tune | codex | skill | active | confirmed/confirmed (confirmed) | 22 | 14,341 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| codex::i::12746fdfd4f2d54f3bcb | unfreeze | codex | skill | active | confirmed/confirmed (confirmed) | 20 | 341 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| codex::i::3ef259ca2b024bb8374f | ios-sync | codex | skill | active | confirmed/confirmed (confirmed) | 19 | 8,037 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| codex::i::48b351d99652a7bf5901 | document-generate | codex | skill | active | confirmed/confirmed (confirmed) | 19 | 11,271 | 0 | 0 次 | 53（Agent内归一） | 超重无refs |
| codex::i::6fc5821ce8d2d7aaef10 | superpowers:dispatching-parallel-agents | codex | skill | active | confirmed/confirmed (confirmed) | 19 | 1,421 | 0 | 0 次 | 36（Agent内归一） | — |
| codex::i::f011280c7c168467c183 | cso | codex | skill | active | confirmed/confirmed (confirmed) | 19 | 3,596 | 0 | 0 次 | 42（Agent内归一） | — |
| codex::i::1a149349bb2a458a1e7a | plan-design-review | codex | skill | active | confirmed/confirmed (confirmed) | 18 | 18,744 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::47e19e11bff44aa0f329 | setup-browser-cookies | codex | skill | active | confirmed/confirmed (confirmed) | 18 | 2,940 | 0 | 0 次 | 40（Agent内归一） | — |
| codex::i::d19aa6070b2f56a2de7a | design-html | codex | skill | active | confirmed/confirmed (confirmed) | 18 | 13,429 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::5061649371495ede248f | guard | codex | skill | active | confirmed/confirmed (confirmed) | 17 | 629 | 0 | 0 次 | 34（Agent内归一） | — |
| codex::i::6c1d72e1d3c9c8fe6c12 | superpowers:writing-plans | codex | skill | active | confirmed/confirmed (confirmed) | 17 | 1,359 | 0 | 4 次 | 32（Agent内归一） | — |
| codex::i::b448cc1b5108ec6e2316 | superpowers:executing-plans | codex | skill | active | confirmed/confirmed (confirmed) | 17 | 504 | 0 | 2 次 | 32（Agent内归一） | — |
| codex::i::c1bd8caadf2aa224526e | skill-creator | codex | skill | active | confirmed/confirmed (confirmed) | 17 | 未确认 | 未确认 | 3 次 | — | — |
| codex::i::f85ea9fb3fdf0b1263c8 | spec | codex | skill | active | confirmed/confirmed (confirmed) | 17 | 13,765 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::fd072abbc79df5528791 | superpowers:requesting-code-review | codex | skill | active | confirmed/confirmed (confirmed) | 17 | 658 | 0 | 0 次 | 34（Agent内归一） | — |
| codex::i::07ffefe5f7a99a0c8adf | freeze | codex | skill | active | confirmed/confirmed (confirmed) | 16 | 768 | 0 | 0 次 | 34（Agent内归一） | — |
| codex::i::2be90cac5f7149de5c39 | superpowers:systematic-debugging | codex | skill | active | confirmed/confirmed (confirmed) | 16 | 2,261 | 0 | 0 次 | 38（Agent内归一） | — |
| codex::i::8d3667109081b765f433 | superpowers:writing-skills | codex | skill | active | confirmed/confirmed (confirmed) | 16 | 5,027 | 0 | 2 次 | 43（Agent内归一） | — |
| codex::i::e9e2e2778b8557d6d3f1 | qa | codex | skill | active | confirmed/confirmed (confirmed) | 16 | 14,903 | 860 | 0 次 | 52（Agent内归一） | — |
| codex::i::4b45cd9bb18d1bd854ec | ios-design-review | codex | skill | active | confirmed/confirmed (confirmed) | 15 | 8,180 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::538708b88b37967655b3 | open-gstack-browser | codex | skill | active | confirmed/confirmed (confirmed) | 15 | 4,341 | 0 | 0 次 | 43（Agent内归一） | — |
| codex::i::69be6fc77ddf626248d0 | hackernews-frontpage | codex | skill | active | confirmed/confirmed (confirmed) | 15 | 293 | 0 | 0 次 | 33（Agent内归一） | 骨架 |
| codex::i::0fce3ec83c8642653aaa | make-pdf | codex | skill | active | confirmed/confirmed (confirmed) | 14 | 4,921 | 0 | 0 次 | 44（Agent内归一） | — |
| codex::i::62991d03c2cc6b39cac0 | context-restore | codex | skill | active | confirmed/confirmed (confirmed) | 14 | 8,837 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::b98e118ad5017ffe2c85 | ios-qa | codex | skill | active | confirmed/confirmed (confirmed) | 14 | 10,517 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::c7e21c259ba3d6b317b7 | lark-attendance | codex | skill | active | confirmed/confirmed (confirmed) | 14 | 386 | 0 | 0 次 | 33（Agent内归一） | 骨架 |
| codex::i::d3c16921a69cd116b84b | codex | codex | skill | active | confirmed/confirmed (confirmed) | 14 | 14,745 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::f7697228a3cc6040db1b | codex:codex-cli-runtime | codex | skill | active | confirmed/confirmed (confirmed) | 14 | 717 | 0 | 0 次 | 34（Agent内归一） | 骨架 |
| codex::i::b4d97e4965db912fc66c | pair-agent | codex | skill | active | confirmed/confirmed (confirmed) | 13 | 10,854 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::b86129631d620a655eb4 | beta | codex | skill | active | confirmed/confirmed (confirmed) | 13 | 18 | 0 | 0 次 | 32（Agent内归一） | 骨架 |
| codex::i::d74f63919b0b59517271 | landing-report | codex | skill | active | confirmed/confirmed (confirmed) | 13 | 8,580 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::fe74598f7d0882a4ac73 | superpowers:test-driven-development | codex | skill | active | confirmed/confirmed (confirmed) | 13 | 2,383 | 0 | 1 次 | 37（Agent内归一） | — |
| codex::i::20bcfbac8f2d5ac19d4f | superpowers:subagent-driven-development | codex | skill | active | confirmed/confirmed (confirmed) | 12 | 2,670 | 0 | 0 次 | 38（Agent内归一） | — |
| codex::i::628a7280d47839bc33bc | codex:codex-result-handling | codex | skill | active | confirmed/confirmed (confirmed) | 12 | 337 | 0 | 0 次 | 32（Agent内归一） | 骨架 |
| codex::i::830f66d4911fd455b3bc | lark-approval | codex | skill | active | confirmed/confirmed (confirmed) | 12 | 341 | 0 | 0 次 | 33（Agent内归一） | 骨架 |
| codex::i::be35ac88475409d87059 | gstack | codex | skill | active | confirmed/confirmed (confirmed) | 12 | 3,540 | 0 | 0 次 | 41（Agent内归一） | — |
| codex::i::bf3de20ee6cdfac17d99 | investigate | codex | skill | active | confirmed/confirmed (confirmed) | 12 | 10,917 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::de1943446d151ea96e9a | benchmark-models | codex | skill | active | confirmed/confirmed (confirmed) | 12 | 3,529 | 0 | 0 次 | 40（Agent内归一） | — |
| codex::i::f465a0a38e444318027f | plan-ceo-review | codex | skill | active | confirmed/confirmed (confirmed) | 12 | 19,054 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::1fac806b5aa6877b077a | office-hours | codex | skill | active | confirmed/confirmed (confirmed) | 11 | 20,455 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::3d32f0b5118d4da2bc81 | ios-fix | codex | skill | active | confirmed/confirmed (confirmed) | 11 | 8,031 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::57efadc102fdfcecd676 | canary | codex | skill | active | confirmed/confirmed (confirmed) | 11 | 13,074 | 0 | 0 次 | 52（Agent内归一） | 超重无refs |
| codex::i::e1b2de2bea1c86f7cc39 | alpha | codex | skill | active | confirmed/confirmed (confirmed) | 11 | 140 | 38 | 0 次 | 32（Agent内归一） | — |
| codex::i::e55017fcd62f7fea810a | careful | codex | skill | active | confirmed/confirmed (confirmed) | 11 | 843 | 0 | 0 次 | 34（Agent内归一） | — |
| codex::i::025b71793715517371b2 | setup-deploy | codex | skill | active | confirmed/confirmed (confirmed) | 10 | 10,665 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::37592a8c761ef8d59cc2 | remotion-best-practices | codex | skill | active | confirmed/confirmed (confirmed) | 10 | 847 | 0 | 0 次 | 33（Agent内归一） | 骨架 |
| codex::i::433bee8c76b419fa2510 | plan-eng-review | codex | skill | active | confirmed/confirmed (confirmed) | 10 | 13,719 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::948a1d7edcb33161a6f2 | review | codex | skill | active | confirmed/confirmed (confirmed) | 10 | 14,811 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::bf4cc9d8247a9af5ebfe | plan-devex-review | codex | skill | active | confirmed/confirmed (confirmed) | 10 | 16,816 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::fb56b59c8772f66838ff | document-release | codex | skill | active | confirmed/confirmed (confirmed) | 10 | 9,765 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::41d32ceb4c1bb31ae41f | qa-only | codex | skill | active | confirmed/confirmed (confirmed) | 9 | 16,106 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::8abdb42abdd8ea62f5b4 | presentations:Presentations | codex | skill | active | confirmed/confirmed (confirmed) | 9 | 3,876 | 3,352 | 0 次 | 41（Agent内归一） | — |
| codex::i::9b0dd446151f95a84e9d | land-and-deploy | codex | skill | active | confirmed/confirmed (confirmed) | 9 | 17,997 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::f8b2774d74f93ad89a6a | devex-review | codex | skill | active | confirmed/confirmed (confirmed) | 9 | 19,154 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::6999dcdbc9ba7bb27500 | gstack-upgrade | codex | skill | active | confirmed/confirmed (confirmed) | 8 | 4,833 | 0 | 1 次 | 42（Agent内归一） | — |
| codex::i::847a23e6d4d1232908e5 | context-save | codex | skill | active | confirmed/confirmed (confirmed) | 8 | 9,434 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::892c67ee8be1c7ca0c6b | retro | codex | skill | active | confirmed/confirmed (confirmed) | 8 | 18,184 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::bffb7bceb361cc2d9ee5 | health | codex | skill | active | confirmed/confirmed (confirmed) | 8 | 11,297 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |
| codex::i::f26b9e77a3f2eeba5ff0 | benchmark | codex | skill | active | confirmed/confirmed (confirmed) | 8 | 7,271 | 0 | 0 次 | 49（Agent内归一） | — |
| codex::i::3e92df2cc8ff778b3e68 | learn | codex | skill | active | confirmed/confirmed (confirmed) | 5 | 8,609 | 0 | 0 次 | 51（Agent内归一） | 超重无refs |

## 三、诊断事实（不替用户执行处置）

### 使用覆盖
| Agent | status | sessions | unreadable | parse errors | undated | matched activations | limitations |
|---|---|---|---|---|---|---|---|
| claude-code | complete | 640 | 0 | 0 | 0 | 61 | — |
| codex | complete | 135 | 0 | 0 | 0 | 112 | — |

- 使用记录：matched 88（173 次激活） / 未匹配 36（76 次） / 歧义 0（0 次）；unmatched/ambiguous 不归入任何组件。
- claude-code：已确认窗口零激活 123；usage 未知 0。
- codex：已确认窗口零激活 181；usage 未知 0。

### 重复候选
- 跨 Agent 维护副本 1472 对：这是安装/发布维护关系，不代表单次会话可节省，也不合并两个 Agent 的 listing 账单。
- 同 Agent 重复候选 1579 对：仅作为人工合并候选，不自动决定 precedence、删除或 winner。
- 跨 Agent：claude-code/claude-code::i::04fba9b234fd88886533 ↔ codex/codex::i::2abd221f1f4185440941（Jaccard 0.998，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::04fba9b234fd88886533 ↔ codex/codex::i::f080e99caa155f5738ea（Jaccard 0.998，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::084d2fd5b2e74de33966 ↔ codex/codex::i::2b560f06c1c9ab68d3f5（Jaccard 1，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::00672f1c06dc667e7b1d（Jaccard 0.657，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::025b71793715517371b2（Jaccard 0.672，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::1b1de97b78620ce845e1（Jaccard 0.632，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::1fac806b5aa6877b077a（Jaccard 0.553，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::2f14b7e1a8a70486887f（Jaccard 0.576，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::3d32f0b5118d4da2bc81（Jaccard 0.705，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::3e92df2cc8ff778b3e68（Jaccard 0.713，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::3ef259ca2b024bb8374f（Jaccard 0.708，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::41d32ceb4c1bb31ae41f（Jaccard 0.585，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::433bee8c76b419fa2510（Jaccard 0.602，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::48b351d99652a7bf5901（Jaccard 0.663，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::4b45cd9bb18d1bd854ec（Jaccard 0.678，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::57efadc102fdfcecd676（Jaccard 0.63，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::62991d03c2cc6b39cac0（Jaccard 0.708，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::847a23e6d4d1232908e5（Jaccard 0.692，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::892c67ee8be1c7ca0c6b（Jaccard 0.567，跨 Agent 维护副本）
- 跨 Agent：claude-code/claude-code::i::085181f415c03afe8d54 ↔ codex/codex::i::8a880abbd584e2f58989（Jaccard 0.664，跨 Agent 维护副本）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::1a82026369bc17a6870f（Jaccard 0.585，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::210a83c76555e1ee4758（Jaccard 0.663，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::23271c2b9119e9e69421（Jaccard 0.681，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::245d8642e4a5e4d3876f（Jaccard 0.659，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::3feea9fe5372515d863e（Jaccard 0.713，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::4bd0d3516d14a997eac3（Jaccard 0.567，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::4dc5ce61a65c01583f11（Jaccard 0.61，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::4fe44eaf69924463d3d1（Jaccard 0.705，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::578e57827e534470c67a（Jaccard 0.575，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::58ebca4f8014d6e91320（Jaccard 0.578，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::5dddef460ffeb587a9e3（Jaccard 0.598，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::66231950afcb27ea108b（Jaccard 0.632，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::73bba65c8002f235725a（Jaccard 0.672，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::777400ba6214edc348e6（Jaccard 0.657，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::7985bf478e3d38e1829d（Jaccard 0.607，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::7d603c7fd3562c64028a（Jaccard 0.708，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::897d01f0629036e00ce9（Jaccard 0.662，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::9e4f7e166f5fa3586ee1（Jaccard 0.714，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::9e8894ca9be2c0ab2f21（Jaccard 0.674，须人工确认）
- 同 Agent：claude-code::i::085181f415c03afe8d54 ↔ claude-code::i::aee952707f6c2b6b6dc4（Jaccard 0.708，须人工确认）

### 结构问题
- 超重无refs 103 / 骨架 28
- 健康候选 2（有直接使用、内容量测完整、无结构/重复信号；仍不等于语义价值已验证）。

<!-- INJECT: Agent 按 references/audit-rubric.md 补充诊断；所有疑似结论保留人工复核。 -->

## 四、高嫌疑名单（每个 Agent 独立归一，跨 Agent 分数不可直接比较）

### claude-code（139 个可排序组件）

| # | instance | runtime | score | Agent 内归一理由 |
|---|---|---|---|---|
| 1 | claude-code::i::46ef92e15526ddb9fb4c | lark-apps | 90 | Agent内always=342tok(归一0.94)；30天少用程度=0.87；body重度=0.84(6728tok/8000) |
| 2 | claude-code::i::ac797e6410363ef78f09 | lark-sheets | 90 | Agent内always=292tok(归一0.81)；30天少用程度=1.00；body重度=0.98(7837tok/8000) |
| 3 | claude-code::i::bb5a72cd550a7fd84695 | skill-production-factory | 86 | Agent内always=362tok(归一1.00)；30天少用程度=0.93；body重度=0.38(3068tok/8000) |
| 4 | claude-code::i::64b466d7f3f53cab7817 | review-analyzer | 81 | Agent内always=334tok(归一0.92)；30天少用程度=1.00；body重度=0.23(1876tok/8000) |
| 5 | claude-code::i::d1ef648e355d8df1e6c4 | zsxq | 80 | Agent内always=290tok(归一0.80)；30天少用程度=0.97；body重度=0.54(4318tok/8000) |
| 6 | claude-code::i::189ab25ef344fad09494 | lark-drive | 74 | Agent内always=204tok(归一0.56)；30天少用程度=1.00；body重度=0.81(6472tok/8000) |
| 7 | claude-code::i::2563e95d2098b91698c2 | buluu-weekly-digest | 74 | Agent内always=275tok(归一0.76)；30天少用程度=1.00；body重度=0.28(2241tok/8000) |
| 8 | claude-code::i::fd26afa95a6156d44c6c | lark-slides | 70 | Agent内always=151tok(归一0.42)；30天少用程度=1.00；body重度=0.95(7598tok/8000) |
| 9 | claude-code::i::b0dc4fb030c114b499c2 | ai-intel-hub | 67 | Agent内always=147tok(归一0.41)；30天少用程度=1.00；body重度=0.84(6681tok/8000) |
| 10 | claude-code::i::f28f854c7bb85c6e4cf8 | neat-freak | 67 | Agent内always=197tok(归一0.54)；30天少用程度=1.00；body重度=0.47(3778tok/8000) |
| 11 | claude-code::i::2f7d2a0375001ed7ce76 | seedance-video-script | 66 | Agent内always=218tok(归一0.60)；30天少用程度=1.00；body重度=0.30(2361tok/8000) |
| 12 | claude-code::i::87fa4111a03184103235 | n8n-mcp-tools-expert | 65 | Agent内always=121tok(归一0.33)；30天少用程度=1.00；body重度=0.91(7317tok/8000) |
| 13 | claude-code::i::20c7a1ffd4d737026de0 | lark-im | 64 | Agent内always=136tok(归一0.38)；30天少用程度=1.00；body重度=0.78(6258tok/8000) |
| 14 | claude-code::i::f77f1f05393f13226f14 | lark-base | 63 | Agent内always=127tok(归一0.35)；30天少用程度=1.00；body重度=0.79(6295tok/8000) |
| 15 | claude-code::i::10ed4ccd17ccfda8d5d9 | n8n-goal-loop | 62 | Agent内always=206tok(归一0.57)；30天少用程度=1.00；body重度=0.16(1296tok/8000) |

### codex（207 个可排序组件）

| # | instance | runtime | score | Agent 内归一理由 |
|---|---|---|---|---|
| 1 | codex::i::550c77809b22c25acf0c | lark-sheets | 90 | Agent内always=292tok(归一0.81)；30天少用程度=1.00；body重度=0.98(7837tok/8000) |
| 2 | codex::i::5555e8a6c75ffa1c69d9 | lark-apps | 89 | Agent内always=342tok(归一0.94)；30天少用程度=0.83；body重度=0.84(6728tok/8000) |
| 3 | codex::i::83cebfba383d8625d3d9 | skill-production-factory | 88 | Agent内always=362tok(归一1.00)；30天少用程度=1.00；body重度=0.38(3068tok/8000) |
| 4 | codex::i::05599777bf13b9a775df | review-analyzer-skill | 81 | Agent内always=334tok(归一0.92)；30天少用程度=1.00；body重度=0.23(1876tok/8000) |
| 5 | codex::i::34cec9b80e07de3d93d9 | zsxq | 81 | Agent内always=290tok(归一0.80)；30天少用程度=1.00；body重度=0.54(4318tok/8000) |
| 6 | codex::i::f02267235a6c780ef53f | using-coze-cli | 80 | Agent内always=227tok(归一0.63)；30天少用程度=1.00；body重度=0.95(7613tok/8000) |
| 7 | codex::i::0cd8927a74e04bf0ff0d | lark-drive | 74 | Agent内always=204tok(归一0.56)；30天少用程度=1.00；body重度=0.81(6472tok/8000) |
| 8 | codex::i::50854c4b74114bae41be | buluu-weekly-digest | 74 | Agent内always=275tok(归一0.76)；30天少用程度=1.00；body重度=0.28(2241tok/8000) |
| 9 | codex::i::454fac2ad68e617ac9bc | design-html | 73 | Agent内always=163tok(归一0.45)；30天少用程度=1.00；body重度=1.00(13840tok/8000) |
| 10 | codex::i::59cb668109e278d248bf | office-hours | 73 | Agent内always=165tok(归一0.46)；30天少用程度=1.00；body重度=1.00(24498tok/8000) |
| 11 | codex::i::a9eea0f898ad3712270d | qa | 72 | Agent内always=158tok(归一0.44)；30天少用程度=1.00；body重度=1.00(16398tok/8000) |
| 12 | codex::i::026fb41aab3011f0711f | autoplan | 71 | Agent内always=149tok(归一0.41)；30天少用程度=1.00；body重度=1.00(18478tok/8000) |
| 13 | codex::i::4352f1cbfb644f6259e5 | plan-devex-review | 71 | Agent内always=151tok(归一0.42)；30天少用程度=1.00；body重度=1.00(22902tok/8000) |
| 14 | codex::i::4ba5c7ee9c8121b48f13 | cso | 71 | Agent内always=150tok(归一0.41)；30天少用程度=1.00；body重度=1.00(16670tok/8000) |
| 15 | codex::i::6ba8dcd7f0a1e20c4700 | devex-review | 71 | Agent内always=151tok(归一0.42)；30天少用程度=1.00；body重度=1.00(14245tok/8000) |

<!-- INJECT: 高嫌疑建议动作；不要跨 Agent 比 priority 分数。 -->

## 五、处置建议（注入位）

<!-- INJECT: 按 references/refactor-playbook.md 写信号、预计收益、风险前提和人工确认框。 -->

## 七、附录：issues 与复核入口

- structured issues 2：agent_not_detected 1 / unsafe_reference_path 1
- legacy warnings 投影 1 条；机器判断只读 issues。
- 注入文件：未加载，占位注释保留。

复核命令（所有账单仍按 Agent 分组）：
- 按 Agent 的 confirmed/inferred/excluded 数量与 token：`jq '.metrics_meta.by_agent' <local-path>/01-metrics.json`
- canonical instance 唯一性：`jq '[.skills[].instance_id] \| length == (unique\|length)' <local-path>/01-metrics.json`
- usage match_status 分桶：`jq '.usage.records \| group_by(.match_status) \| map({status:(.[0].match_status // "legacy"),n:length})' <local-path>/00-inventory.json`
- 跨 Agent 维护副本候选：`jq '[.skills[] as $s \| $s.duplication[]? \| select(.relation=="cross_agent_maintenance_copy") \| {from:$s.instance_id,to:.with}]' <local-path>/01-metrics.json`
