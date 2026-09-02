# 重启恢复手册

写于 2026-09-02。这份文件本身在 git 里,重启一定还在。

## 一句话状态

所有工作都已提交。重启不会丢任何代码。

- 主线:`crossaudit_integ` 仓库,分支 `v5-redesign`,HEAD = `e24f29a`
- 决策记录:`docs/DECISIONS.md`,D39–D147 连续无缺口(有测试守着)
- 打好的安装包:`~/Documents/Crossaudit/builds/CrossAudit-4.15.0-arm64.dmg`(146M,sha256 前 16 位 `d14e354c36c61614`)

## 重启会消失的东西(都不要紧)

| 东西 | 影响 |
|---|---|
| 10 个 herdr agent 面板 | 全部关闭,需要时重新拉起即可,它们的产出都已经在 git 分支上 |
| 3 个挂载的 DMG 卷 | 自动卸载,包本身已存到 builds/ |
| 临时目录 `/private/tmp/...scratchpad`(4.4G) | 可能被系统清掉。里面是构建产物和历史 prompt,都可重建 |
| 15 个 worktree 里的未提交改动 | **故意丢弃**:11 处是突变测试特意改的那一行,4 处是 `.venv` 构建产物,没有真实工作 |

## 远端(GitHub)现状

- `crossaudit-app/main` = `7ded699` — 你原来的版本,我推的已按你要求撤回
- `crossaudit-app/codex/evidence-governance-fusion` = `dd725d3` — 未动
- 我那 332 个提交只在本地 `v5-redesign` 上,没推

## 重启后怎么恢复

1. 开终端,进目录:

       cd ~/Documents/Crossaudit/crossaudit_integ

2. 确认状态没变(应当输出 `e24f29a` 和空的改动列表):

       git log --oneline -1 && git status --short

3. 开 Claude Code,把这句话丢给它:

       读 docs/RESTART.md,从"下一步"那一节继续。

4. 需要跑测试的话,用共享解释器(不要用系统 python):

       /Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python -m pytest -q

5. 需要重新打包:

       bash packaging/macos/build_dmg.sh

## 下一步(按优先级)

1. **逐文件对比我这条线和 `codex/evidence-governance-fusion`(未做完)**
   已看 3 个文件(`repair_guard.py`、`generator.py`、`receipt/verify.py`),初步结论是**两条线互补不冲突**:
   codex 那条从"检测防御性编程"和"模型单方面的判定不能自动变成修复指令"入手;
   我这条从"消除产生防御性编程的激励"入手(废掉只能咨询的宪法、finding 状态、prompt 侧重)。
   还没看完 18 个文件里剩下的 15 个。

2. **三个已完成但没独立复核的分支**(按你上次选 B,先扣住不合):
   `fix/approximately-means-approximately`、`fix/guard-name-states-its-reach`、`feat/finding-states`

3. **`docs/dcl-lifecycle-states` 分支必须先 rebase 再看**
   当前形态会删掉 68 个文件、9534 行(含诚实性守卫的测试文件),而测试全绿——
   这是靠人读文件清单发现的,不是靠守卫。合之前必须重做。

4. **打包版上仍开着的用户可见问题**
   - 输入框在辅助功能树里没有名字(旁边的搜索框有,它没有)
   - 479 条拒绝/报错文案没有中文
   - 测试套件里有一处会通过 `gh` 联网,套件不该需要网络

## 不可动摇的规矩(别让任何人改掉)

- `auditor/ broker/ ledger/ policy/ dcl/` 是审计内核,只能加不能削,必须向后兼容
- 没有 agent 可以复核自己写的东西
- 合并门槛三条同时成立:独立复核干净 + 全量测试在宿主机上绿 + 内核规矩没被动
- 推送 / 发布 / 删数据这类不可逆的事,先问你
