# 重启恢复手册

写于 2026-09-02。这份文件本身在 git 里,重启一定还在。

## 一句话状态

所有工作都已发布：本地分支 `fusion/evidence-authority` 与 GitHub 仓库 `crossaudit-harness` 的 main 同步。
`v5-redesign` 未动；要不要把融合线合回它由你定。

- 决策记录：`docs/DECISIONS.md`，D39–D149 连续无缺口（有测试守着）
- 融合方案与逐文件对比：`docs/findings/codex-fusion-dd725d3.md`（含三份分簇报告）
- 设计文档：`docs/EVIDENCE_AUTHORITY.md`；DESIGN.md §7.1；README 两个档位说明
- 打好的安装包：`~/Documents/Crossaudit/builds/CrossAudit-4.16.0-arm64.dmg`（153M，sha256 前 16 位 `5f3f46387167c230`，来自发布后的 main（含 Thinking Orbs））；上一版 4.15.0 仍在同目录

## 融合线做了什么（2026-09-02）

| 切片 | 内容 | 状态 |
|---|---|---|
| A | 合入 `feat/finding-states`，复核后修了 5 处（sidecar 未 git add、状态词进了模型 prompt 等） | 已合 |
| B+C | `auditor/authority.py` 证据授权层（判定阶梯不动，其后派生）、回执 `authority` 块、档位 `authority.lone_model_blocker` | 已合，复核 9 处已修 |
| D | `repair_guard.py`：硬拒绝只剩越界文件与非渲染二进制，其余为"提醒"送入下一轮审计 | 已合，两轮复核 20 处已修 |
| E | 文档 | 已合 |
| 搁置分支 | `fix/approximately-means-approximately`、`fix/guard-name-states-its-reach` 复核后修好合入；套件不再联网 | 已合 |
| 控制台 | 决策卡文案、发现的层级标注、无障碍名、拒绝文案中文接线 | 已合，第 3 轮体验修复见下 |
| 中文化 | 540 条拒绝文案 538 条有中文；语言解析改为所有命令生效 | 见下 |

## 重启后怎么恢复

1. `cd ~/Documents/Crossaudit/crossaudit_integ && git checkout fusion/evidence-authority && git status --short`
2. 开 Claude Code：`读 docs/RESTART.md，从"下一步"继续。`
3. 跑测试必须带 PYTHONPATH（共享 venv 里装着旧包）：

       PYTHONPATH=$PWD/src /Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python -m pytest -q tests/

4. 打包：`PYTHON_BIN=/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python bash packaging/macos/build_dmg.sh`
5. 浏览器实测控制台时，Claude in Chrome 有两个已连接的 Chrome 实例，选 "macbook"。

## 第二轮（2026-09-03）

| 切片 | 内容 | 状态 |
|---|---|---|
| 感知延迟 | 发送即返回（~3 ms），每阶段叙述，流式默认开启、Anthropic 流式，审计阶段逐项检查，8 秒静默心跳 | 已合，复核修复已合 |
| 安装与预检 | 缺凭据前置设置卡（所有入口）、异厂商句子、向导默认单仓库、DMG 打开说明、卸载说明 | 已合，复核修复已合 |
| 结果与决策 | 人话判定、观察句优先、详情折叠、耗时费用预估、每个升级分支有原因与动作 | 已合，复核修复已合 |
| 预警与计费 | 归属到任务/循环/轮次/角色、80%/95% 预警、429 倒计时、顶栏胶囊、未计价可见与覆盖价、导出与汇总 | 已合，复核修复已合 |
| 闭环复核 | 两轮闭环审计（e0e3b36、e3b9388），其后两处遗留已修 | `docs/findings/fusion-round2/review-closure*.md` |

## 发布（2026-09-03）

- 公开仓库：https://github.com/dongzhaohe321418-lab/crossaudit-harness （main = 融合线完整历史，CI 在 Linux/macOS 全绿，Windows 为咨询性）
- Release：https://github.com/dongzhaohe321418-lab/crossaudit-harness/releases/tag/v4.16.0 （DMG + sha256；临时签名、未公证）
- 官网源码在 `website/`，线上 `crossaudit-v4.vercel.app`；内容已按 4.16.0 更新，截图由 `website/scripts/shoot-console.mjs` 重新生成
- Thinking Orbs（MIT）已内置：`src/crossaudit/console/vendor/thinking_orbs_engine.js`，`scripts/vendor_thinking_orbs.py` 重新生成

## 下一步（按优先级）

1. **官网部署**：需要你先 `cd website && npx --yes vercel@58.9.4 login`，然后 `npx vercel link`（选现有项目 crossaudit-v4）并 `npm run release:vercel`；或在 Vercel 控制台把 Git 集成改连到 crossaudit-harness。
2. **公证**：`CROSSAUDIT_PUBLIC_RELEASE=1` + Developer ID + notarytool profile 重新打包，替换 Release 资产，官网与 README 去掉"右键打开"说明。
3. **Windows 移植**（可选切片）：CONTRIBUTING.md "Windows" 一节列出的五类问题。
4. `docs/dcl-lifecycle-states` 分支仍需先 rebase 再看（会删 68 个文件），未动。
5. 待定的产品问题：`lone_model_blocker` 的默认何时切到 `escalate`；`generator_streaming` 是否也该管审计端进度。

## 不可动摇的规矩(别让任何人改掉)

- `auditor/ broker/ ledger/ policy/ dcl/` 是审计内核,只能加不能削,必须向后兼容
- 没有 agent 可以复核自己写的东西
- 合并门槛三条同时成立:独立复核干净 + 全量测试在宿主机上绿 + 内核规矩没被动
- 推送 / 发布 / 删数据这类不可逆的事,先问你
