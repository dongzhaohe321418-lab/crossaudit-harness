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

## 下一步（按优先级）

1. **收尾中的两项**：控制台第 3 轮体验修复（模态挡住语言开关、原始秒数、术语、审查卡按钮）在分支 `fusion/console`；中文化复核修复（所有命令的语言解析、Denial 子类覆盖、术语对齐、供应商失败句子）在 `fusion/i18n-denials`。合入后跑全量。
2. **最终交付**：版本升 4.16.0、CHANGELOG、`scripts/release_gate.sh`、打 DMG 到 `dist/` 并复制到 `~/Documents/Crossaudit/builds/`。
3. **合回主线与发布**由你定：`git merge fusion/evidence-authority` 到 `v5-redesign`；推送/发布前先问。
4. `docs/dcl-lifecycle-states` 分支仍需先 rebase 再看（会删 68 个文件），未动。
5. 待定的产品问题：`lone_model_blocker` 的默认何时切到 `escalate`，等 finding-states 跑出确认率。

## 不可动摇的规矩(别让任何人改掉)

- `auditor/ broker/ ledger/ policy/ dcl/` 是审计内核,只能加不能削,必须向后兼容
- 没有 agent 可以复核自己写的东西
- 合并门槛三条同时成立:独立复核干净 + 全量测试在宿主机上绿 + 内核规矩没被动
- 推送 / 发布 / 删数据这类不可逆的事,先问你
