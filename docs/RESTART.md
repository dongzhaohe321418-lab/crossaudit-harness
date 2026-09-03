# 重启恢复手册

写于 2026-09-02。这份文件本身在 git 里,重启一定还在。

## 一句话状态

所有工作都已提交在本地分支 `fusion/evidence-authority` 上（`crossaudit_integ` 仓库）。
`v5-redesign` 未动；融合分支合不合回主线由你定。

- 决策记录：`docs/DECISIONS.md`，D39–D149 连续无缺口（有测试守着）
- 融合方案与逐文件对比：`docs/findings/codex-fusion-dd725d3.md`（含三份分簇报告）
- 设计文档：`docs/EVIDENCE_AUTHORITY.md`；DESIGN.md §7.1；README 两个档位说明
- 上一个打好的安装包：`~/Documents/Crossaudit/builds/CrossAudit-4.15.0-arm64.dmg`；融合线的新包在 `dist/`（见"最终交付"）

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
| 闭环复核 | 第二轮闭环审计在 e3b9388 上进行 | 见 `docs/findings/` 或 scratchpad 的 review-closure2.md |

## 下一步（按优先级）

1. **第二轮闭环复核**若有未关项，派回修；否则重新打包 4.16.0 DMG，复制到 `~/Documents/Crossaudit/builds/`。
2. **GitHub 就绪切片**：README 首屏与演示、与 Codex/Claude Code 类 harness 的对比表、CI 徽章、CONTRIBUTING、issue 模板；公证发布需要你的 Apple 开发者身份。
3. **合回主线与发布**由你定：`git merge fusion/evidence-authority` 到 `v5-redesign`；推送/发布前先问。
4. `docs/dcl-lifecycle-states` 分支仍需先 rebase 再看（会删 68 个文件），未动。
5. 待定的产品问题：`lone_model_blocker` 的默认何时切到 `escalate`，等 finding-states 跑出确认率；`generator_streaming` 是否也该管审计端进度（延迟复核 D9）。

## 不可动摇的规矩(别让任何人改掉)

- `auditor/ broker/ ledger/ policy/ dcl/` 是审计内核,只能加不能削,必须向后兼容
- 没有 agent 可以复核自己写的东西
- 合并门槛三条同时成立:独立复核干净 + 全量测试在宿主机上绿 + 内核规矩没被动
- 推送 / 发布 / 删数据这类不可逆的事,先问你
