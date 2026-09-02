# 报告 C — 重叠簇：cli/build.py · cli/main.py · console/overview.py · console/page.py · generator.py · repair_guard.py

范围：codex 提交 `dd725d3`（分支 `crossaudit-app/codex/evidence-governance-fusion`）vs 主线 `v5-redesign` HEAD `c170c17`，merge-base `7ded699`。只读分析，未改任何 tracked 文件。

## 0. 一句话结论

codex 在这几个文件里做的事只有三件：**(1)** 审计 BLOCKED 后只把 `DCL:` 前缀的 BLOCKER 回传给 Generator（`render_findings(verified_only=True)`）并据此算出 `repair_scope`；**(2)** 修复轮提交前用 `RepairGuard.assess(git diff --cached)` 筛范围/行数/防御性模式，拒绝则 `git restore --staged` + `[BLOCKER]` 反馈；**(3)** 把 `outcome.authority`（status/route）打到 receipt、`--json`、人读输出、报告表格、console 流水线 Verdict 步、升级卡 `requested` 文案。**没有新增 CLI flag。**

主线 HEAD 对应位置全部还在，且轮结构（`for round_no in range(1, cfg.max_rounds + 1)`）没变；但 HEAD 把 apply→stage→commit 包进了 `with written:`（`AppliedFiles` 事务作用域，`finalize()` 唯一成功出口），并新增了结构化升级 `kind`/`cause` 通道和 Decision Center 文案槽位。因此 codex 的 hunk 文本上都不能直接 apply（`generator.py` 的三处例外），但**意图全部可以在 HEAD 的既有函数上重实现，且不需要新增任何 UI 元素**。

关键跨簇依赖：`build.py` 的 `verified_only` 过滤**语义上依赖** codex 对 `auditor/run.py` 的改动（孤立模型 BLOCKER → `ESCALATE` 而不是 `BLOCKED`）。`auditor/` 是 additive-only 内核包，这一条要么在 A/B 簇以 additive 方式落地（`AuditOutcome.authority` 默认空 + 配置开关），要么在 `build.py` 内用一个 build 侧等价分支兜底（见 §2(d) 方案 B）。

测试基线：`pytest -k "build or console or main or cli"` → **194 passed, 1862 deselected, 51s**（需 `PYTHONPATH=src`，否则 venv 解析到 crossaudit_v4 的旧包，`crossaudit.broker` 缺失即 collect error）。

---

## 1. codex 的意图（读 `authority.py` / `repair_guard.py` / `docs/EVIDENCE_GOVERNANCE_FUSION.md` 后的提炼）

- `src/crossaudit/authority.py`（新，254 行）：把 DCL findings 和模型 findings 归一为 `EvidenceRecord`（`verified=True` 仅限 registered checker；模型 finding `evidence_type="textual_judgment"`, `verified=False`）。`decide()` 产出 `AuthorityDecision`：
  - `BLOCK/BLOCKED/automatic-repair`：仅当存在 verified BLOCKER（hard evidence）或跨 producer + 跨 mechanism 共识；
  - `ESCALATE/ESCALATE/git-governance`：escalation_lock、完整性错误、coverage 不完整、非证据 provider、Auditor 自请升级、**或只有模型 BLOCKER**；
  - `ESCALATE/DCL_ONLY/obtain-audit`：无模型；
  - `ADVISORY|PASS / PASS / admission`。
  - `validate_block()` 供 receipt verifier 校验 digest 与 status↔verdict 映射。
- `src/crossaudit/repair_guard.py`（新，110 行）：`RepairGuard(max_changed_lines=200).assess(unified_diff, allowed_files, locally_rendered_files=)` → `RepairAssessment(allowed, changed_files, changed_lines, unsupported_files, defensive_patterns, reasons)`。五个正则：`broad_exception`、`silent_pass`、`retry_or_fallback`、`suppression`、`disabled_assertion`。
- `config.py`：新增顶层 `repair: {enabled: bool=True, max_changed_lines: int=200}`（`RepairPolicy`），scaffold 模板同步。
- 文档核心句："Only verified machine blockers are returned to the Generator automatically… A guard refusal does not delete the working bytes."

---

## 2. `src/crossaudit/cli/build.py`

### (a) codex 做了什么（43 行）
1. `from ..repair_guard import RepairGuard`
2. 循环前：`repair_scope: set[str] | None = None`（None=非修复轮；空集=DCL 失败指向整个 increment；否则只允许命名的 artifact 移动）。
3. apply 后：`model_written = set(written)`；`render_export` 后：`locally_rendered = set(written) - model_written`。
4. `staged` 非空后、commit 前：若 `repair_scope is not None and cfg.repair.enabled` → `allowed = set(repair_scope) or set(staged)`；`diff = git("diff","--cached","--binary","--no-ext-diff")`；`RepairGuard(cfg.repair.max_changed_lines).assess(diff, allowed, locally_rendered_files=locally_rendered)`；拒绝则 `git restore --staged -- *staged`，`emit("repair_refused","evidence gate",…, state=RunState.REVISING)`，`findings = "[BLOCKER] The evidence-bound repair guard refused the last revision: …"`；末轮则 `termination_reason=…; break`，否则 `continue`。
5. 审计 BLOCKED 后：`findings = gen_mod.render_findings(_last_report(cfg), verified_only=True)`；`blockers = [artifact for DCL: BLOCKER in parse_findings(...)]`；`broad = any(a in ("increment","?","invalid Auditor reply"))`；`repair_scope = set() if broad else set(blockers)`。

### (b) 主线 HEAD 现状（`run_loop`, 437–1064 行）
| codex 触点 | HEAD 位置 | 备注 |
|---|---|---|
| 反馈变量 | `findings = ""`（572）；喂给 `_current_work(cfg, task, findings, context_report)`（634，`shape_work` 用它决定哪些文件保持全文）和 `gen_mod.generate(findings=findings)`（641） | 同一个字符串变量，语义未变 |
| 合成 `[BLOCKER]` 反馈 | 777（生成被拒）、818/843（文档导出被拒）、869（byte-identical 自愈一次） | HEAD 已有多个"机械拒绝 → [BLOCKER] 文本"先例，guard 拒绝可直接沿用该模式 |
| apply / render | `written = gen_mod.apply(work, cfg.root, cfg.scope_dirs)`（815）；`rendered = document_export.render_export(cfg.root, written, task)`（829）；HEAD 要求 `rendered is written`（`AppliedFiles.replace_with` 原地换 entries） | `set(written)` 在 render 前后取差即得 `locally_rendered`，与 codex 完全同构 |
| staging | `_stage_generated(cfg, written)`（860）→ `_stage_authorized`（291，`hash-object -w` + `update-index --index-info`，注册 index 回滚）；返回 `git diff --cached --name-only` | staged 路径列表就是 codex 的 `staged` |
| 已有的 staged-diff 筛查 | `_staged_secret(cfg)`（886；读 `git diff --cached --unified=0`，`_MAX_SCAN_BYTES=512K`） | **这就是 guard 的天然插入点**：同一时机、同一个 diff 读取 |
| commit | 902–915，`git commit -q -m … -m CrossAudit-Generator: … -m CrossAudit-Chat: …` | |
| 成功出口 | `written.finalize()`（937） | `with written:` 内任何 `continue/break/raise` → `rollback()` **同时还原文件系统和 index**（858 行注释） |
| 轮限 | `if round_no == cfg.max_rounds: break`（807/821/846）；`no_progress_retry_used`（自愈一次） | 轮结构与 codex 一致 |
| 审计 BLOCKED → 回传 | 973–977：`emit("audit_blocked")`；`findings = gen_mod.render_findings(_last_report(cfg))`；`emit("revision_requested")` | **HEAD 不过滤**：模型 BLOCKER 与 DCL BLOCKER 一起原样回给 Generator |
| 停机记录 | `record_decision_object()`（981）：`cause` ∈ {budget, provider_unavailable, answered, generator_format, generator_refused, no_progress, ""} → `store.escalate(..., kind, cause)` | 新 cause 可 additive 加入 |

### (c) 关系：**互补，但有一处语义冲突**
- 过滤回传 + repair_scope：互补，HEAD 完全没有。
- guard 插入点：互补，`_staged_secret` 已经证明"commit 前筛 staged diff"这条路在 HEAD 是通的。
- **冲突点**：codex 承诺"guard 拒绝不删工作区字节，下一轮 Generator 能看到并修小"；HEAD 的 `with written:` 事务在 `continue` 时会把文件系统也回滚（`AppliedFiles.rollback()`），Generator 下一轮的 `THE WORK AS IT STANDS` 看不到被拒的尝试。两种语义二选一（见 (d) 第 3 点）。
- 第二个隐含冲突：HEAD `auditor/run.py` 对孤立模型 BLOCKER 仍给 `BLOCKED`（`verdict = reply["verdict"]`，257 行）。若只把 `verified_only=True` 搬进 build.py 而 auditor 不变，则"模型 BLOCKED 且无 DCL BLOCKER"这一轮会把 `"(no verified automatic-repair finding)"` 回给 Generator 要求修订——空修复轮，白烧预算。

### (d) 融合配方（全部落在 `run_loop`）
1. **`repair_scope`/过滤**（973–977 处）：
   ```python
   report = _last_report(cfg)
   findings = gen_mod.render_findings(report, verified_only=True)
   verified = [f for f in parse_findings(report)
               if f.severity == "BLOCKER" and f.rule.startswith("DCL:")]
   broad = any(f.artifact in ("increment", "?", "invalid Auditor reply") for f in verified)
   repair_scope = set() if broad else {f.artifact for f in verified}
   ```
   `parse_findings` 从 `..dispute` 顶层 import（overview.py 已这样做，无循环依赖）。
2. **方案 B（build 侧兜底，不动 `auditor/`）**：在同一处，若 `not verified`（BLOCKED 但零 DCL BLOCKER = 模型独断）→ 不再 `continue` 回 Generator，而是 `termination_reason = "the auditor's blocker is a model proposal without reproduced evidence; it needs human judgment"`，新增局部标记 `governance_stop = True`，跳出循环，让 `record_decision_object()` 以 `kind="audit"`、`cause="evidence_governance"` 记录。这与 codex 的 `git-governance` 路由等价，且 cycle 状态由 BLOCKED 经 `store.escalate` 变 ESCALATED（`no_progress` 停机已走同一条路）。若 A/B 簇把 `AuditOutcome.authority` additive 地加进 `auditor/run.py`，方案 B 退化为读 `latest`（cycle 快照）/receipt 里的 route，逻辑不变。
   - 产品决策提示：memory 里的定位是"strictness 是可选拨盘"。建议此行为受 `cfg.repair`（或 strictness tier）控制，默认值由用户定；HEAD 测试 `test_three_cli_build_revisions_remain_one_cycle_and_end_escalated`（tests/test_loop_integrity.py:255）直接断言模型 BLOCKED 可跑满三轮，开启后需按 codex 那样改测试。
3. **guard 调用点**（`_staged_secret` 之后、`try: commit` 之前，886–901 之间）：
   ```python
   if repair_scope is not None and cfg.repair.enabled:
       allowed = set(repair_scope) or set(staged)
       assessment = RepairGuard(cfg.repair.max_changed_lines).assess(
           git("diff", "--cached", "--binary", "--no-ext-diff", cwd=cfg.root, check=False)[:_MAX_SCAN_BYTES],
           allowed, locally_rendered_files=locally_rendered)
       if not assessment.allowed:
           emit("repair_refused", "loop", "automatic repair refused", detail, state=RunState.REVISING)
           findings = "[BLOCKER] The repair guard refused the last revision: …"
           ...  # continue / break → with-scope 自动回滚 index + 文件
   ```
   - `model_written = set(written)` 放 815 行 apply 后；`locally_rendered = set(written) - model_written` 放 829 行 render 后（`AppliedFiles` 可迭代出 relative path）。
   - **不要**手写 `git restore --staged`：HEAD 的 `written.rollback()` 已经通过 `_index_rollback` 精确还原 index，而且比 `restore --staged` 更安全（不碰用户先前 staged 的无关条目，这正是 HEAD 909 行注释强调的）。
   - 语义取舍：建议接受 HEAD 事务语义（拒绝即整体回滚），把被拒 diff 的**摘要**（改动文件、行数、命中模式）写进 `findings` 文本，Generator 下一轮得到的信息比"字节留在工作区"更精确，也不破坏 `finalize()` 唯一成功出口的不变量。若坚持 codex 的"字节可见"，需要给 `AppliedFiles` 加一个"保留文件、只回滚 index"的方法——改 `file_identity.py`，不推荐。
   - 防死循环：拒绝后回滚，下一轮若 Generator 交回同样字节会再次 staged→再次拒绝，直到 `max_rounds`。仿照 `no_progress_retry_used`，加 `repair_refusal_used` 只免费重问一次，第二次拒绝即停机，`cause="repair_refused"`。
4. **停机 cause**：`record_decision_object()` 的 cause 链新增 `"repair_refused"` 和 `"evidence_governance"`（`controller/state.py` 的 `escalate()`/`record_build_escalation()` 已透传 `cause[:64]`，无需改控制器）。
5. **配置**：`Config.repair: RepairPolicy` 按 codex 原样加进 `config.py`（`_ALLOWED_TOP` + 校验 + scaffold 模板）；`config.py` 不在内核包名单内。

### (e) 内核触碰
`build.py` 本身：无。仅 import `..repair_guard`（新模块）、`..dispute.parse_findings`（已有）。**但**过滤语义依赖 `auditor/run.py` 的 verdict 变化（见 §6）。

---

## 3. `src/crossaudit/cli/main.py`

### (a) codex 做了什么（27 行，无新 flag）
- `_provider_stop_reason(outcome)`：新增分支 `outcome.authority["status"] == "ESCALATE"` → `"evidence authority: {rationale[0][:380]}"`。
- `cmd_audit`：`build_receipt(..., authority=outcome.authority)`；`result["authority"] = {status, route, policy_version}`；人读输出加一行 `authority: X -> route`。
- `cmd_run`：`build_receipt(..., authority=...)`；`print(f"  AUTHORITY: {status} -> {route}")` 紧跟 `VERDICT:` 行。

### (b) 主线 HEAD 现状
- `_provider_stop_reason`（849）与 merge-base 相同，但旁边多了 `_provider_stop_kind`（865）——HEAD 已把"升级类型"结构化为 `escalation_kind`（provider/budget/audit），Console 按字段路由而不是解析句子；codex 的字符串前缀方案是 merge-base 时代的做法。
- `cmd_audit` 的 receipt 构造在 971–981（`integrity=outcome.integrity` 收尾），JSON `result` 在 1010–1013，人读 `human` 在 1014–1017。
- `cmd_run` 的 receipt 构造在 1668–1678，`VERDICT:` 打印在 1698，其后是按 verdict 分支的"What blocked it / Next / Escalated"提示（1701–1719）。
- `record_verdict(...)` 签名：`escalation_reason=, escalation_kind=, constitution_commit=`，**无 `cause`**。

### (c) 关系：**可直接吸收（结构性小改）**
### (d) 配方
1. `_provider_stop_reason`：加 codex 的第二分支即可（`getattr(outcome, "authority", {})` 防旧 outcome）。`classify_escalation_kind` 对该句返回 `"audit"`，正确。
2. 若要结构化：`controller/state.py::StateStore.record_verdict` additive 增加 `escalation_cause: str = ""`，`cmd_audit`/`cmd_run` 传 `"evidence_governance"`；Decision Center 便能直接按 `row.cause` 切文案（见 §4）。
3. receipt：`build_receipt(..., authority=getattr(outcome, "authority", None))`——`receipt/build.py::build` 的 `integrity: str = "OK"` 旁加 `authority: dict | None = None`（receipt 簇负责）。
4. `--json`：在 1010 行 `result` 加 `"authority": {...}`（只在存在时）。
5. 人读输出：`cmd_run` 1698 行后加 `AUTHORITY:` 行——**建议不加**独立行，改为在既有的 `Escalated: {invalid_reason or …}` 分支（1717）里把 rationale 作为那句的内容；CLI 输出与 console 同一原则：一个判定、一句原因，不引入第二套词汇。`cmd_audit` 的 `human` 同理只在 ESCALATE 时附 `rationale[0]`。

### (e) 内核触碰：无。

---

## 4. `src/crossaudit/console/overview.py` + `console/page.py`

### (a) codex 做了什么
- overview：`AUTHORITY_RE` 解析报告表格行 `| evidence authority | **X** via \`route\` |`；`Cycle.authority`/`authority_route` 字段；`pipeline()` 的 Verdict 步 detail 变为 `"{verdict} · authority {status} -> {route}"`；`escalations()` 当 `latest.authority_route == "git-governance"` 时 `requested` 换成 "Review the proposed blocker and its evidence. Dispute a misreading, reopen with a recorded reason, or stop without admission."；`attempts[]` 每项加 `authority`/`route`。
- page.py：只加了那句 `requested` 的 ZH 译文（+1 行）。

### (b) 主线 HEAD 现状
- overview.py（430 行）：`Cycle` 新增 `report_state`/`report_note`（F1/R2：只渲染审计过的字节并标注漂移）；`read_cycles` 经 `read_report_sources` 读 receipt 引用的 commit；`pipeline()` 五步结构与 detail 文案与 merge-base 同形（Verdict 步 detail 仍是 `f"{latest.verdict} · {len(latest.findings)} finding(s)"`，213 行）；`escalations()` 增加 `kind`/`cause`/`remediations`（`errors.ESCALATION_REMEDIATIONS`: provider/budget/audit），`requested` 三选一（有 issues / provider_failure / 其他）。
- page.py（8077 行）：
  - 升级卡 `openResolution(...)`（4597–4680）：按 `row.kind`（budget/provider）和 `row.cause`（generator_format/generator_refused/no_progress/answered）选择 `resolution-flag`/`-title`/`-summary`/`-limit-*`/`-request`/`-reopen-*` 文案；`attempts` 渲染为 `.decision-attempt`（round · N issues · verdict word）；`row.requested` 是 `resolution-request` 的兜底。
  - 流水线：live run card `loop-step`（5958–5963，`s.title`/`s.detail`）和 Plan tab `plan-step`（6258）。
  - ZH 字典：`"Tell the generator how to correct…"` 在 3291 行；`"Verdict":"判定"` 在 3560 行。
  - 翻译边界测试（tests/test_console_translation_boundary.py）会枚举服务端字面量与 JS 拼接短语，**任何新英文句子必须有 ZH 条目**。

### (c) 关系：**互补；codex 的展示方式与设计哲学有一处抵触**
`docs/design/VISUAL_DECISION_SYSTEM.md` §2 "审美主要体现在删除"明确要删的项包括"没有决策价值的状态"和"用户不理解的审计副产物"。`"BLOCKED · authority BLOCK -> automatic-repair"` 在一个 detail 里并置两套状态词汇（workflow verdict 与 authority status），正是被点名的副产物；`route` 字符串（`automatic-repair`/`git-governance`/`obtain-audit`）是内部路由名，对用户无决策价值。codex 的 `requested` 文案变体则**有**决策价值（告诉人可以 dispute/reopen/stop），应吸收。

### (d) 配方（零新增元素）
1. overview.py `read_cycles`：additive 加 `Cycle.authority`/`authority_route`。来源优先读 `receipt.json["authority"]`（`_cited_report_commit` 已在读同一个文件；结构化且被 verifier 绑定），报告表格正则作后备。仅当 A/B 簇真的往 report/receipt 写这块时才有值；否则字段保持 `""`，页面无变化。
2. `pipeline()` Verdict 步：**不改** detail 格式。若要表达"需要人判断"，改 `state`：`failed=verdict in ("BLOCKED","ESCALATE")` 已经覆盖，无需动。
3. `escalations()`：`requested` 的分支顺序改为 `if cause == "evidence_governance" or latest.authority_route == "git-governance": <codex 句>` 优先于 `elif issues:`。`attempts[]` **不加** authority/route 列（每行的决策价值为零）。
4. page.py `openResolution`：加一个 `const governance=row.cause==='evidence_governance'` 分支，复用既有槽位：flag "Auditor raised a concern that needs your judgment"，title "The audit needs your decision"（已存在），summary 用 rationale 化的一句（"The auditor's blocker is a model reading without reproduced evidence. CrossAudit does not let a model-only claim drive automatic rewrites."），request 用 codex 那句。`resolution-issues` 已展示 finding 的 rule/artifact/observation——证据本身已在屏上，不需要新卡。
5. ZH 字典：为 codex 的 `requested` 句加译文（codex 已给出：`"请审查这项阻断建议及其证据。若属于误读可提出争议，也可记录理由后重开，或停止且不准入。"`），以及上面新增的 flag/summary 两句。放在 3291 行同一块。
6. 升级 remediations：`errors.ESCALATION_REMEDIATIONS["audit"] = (REVISE, STOP)` 保持；若产品想在卡上直接给"Dispute"按钮，那是新的 `RemediationAction`，属于另一个决策，本次不做。

### (e) 内核触碰：无（`errors.py`、`controller/` 不在名单内）。

---

## 5. `src/crossaudit/generator.py` 与 `src/crossaudit/repair_guard.py`

### (a) codex 做了什么
- `GENERATOR_SYSTEM`：把"When findings are shown to you, address every BLOCKER… route it as a dispute"三行换成"Findings returned automatically are verified mechanical failures… Do not make a check disappear by adding broad exception handling, silent fallbacks, retries, suppressions, skipped tests, or relaxed assertions… stop in `notes`"。
- `render_findings(report, *, verified_only=False)`：`verified_only` 时用 `dispute.parse_findings` 只留 `severity=="BLOCKER" and rule.startswith("DCL:")`，重排成 `### [BLOCKER] rule — artifact\nobservation`，空则 `"(no verified automatic-repair finding)"`。
- `build_prompt`：findings 段标题改 `VERIFIED FAILURES FROM THE LAST ROUND`，指令加"minimal causal repair… Do not add broad catches, fallbacks, retries, suppressions or disabled tests"。
- `repair_guard.py`：全新模块，无主线对应物。

### (b) 主线 HEAD 现状
generator.py 长了 +368 行（`bind_file_identities`、`ToolRequest`/`ComputeRequest`、`_conversational_answer`、STAY ON TASK 复述、outline 折叠），但 **`render_findings`（328–344）和 `build_prompt` 的 `if findings:` 块（438–441）与 merge-base 逐字相同**，`GENERATOR_SYSTEM` 第 40–42 行也是 codex 替换的那三行原文。`generate(findings=…)` → `build_prompt(findings=…)` 管线未变。HEAD 无任何 `verified`/`authority` 概念（grep 确认；src 内 "authority" 全是 "authorization receipt / 权威来源" 的普通用词）。

### (c) 关系：**可直接吸收**（三处 hunk 基本能文本 apply）；`repair_guard.py` 是纯新增。

### (d) 配方与注意点
1. `render_findings` / `build_prompt` / 系统提示三处按 codex 原样吸收；`parse_findings` 在函数内延迟 import（codex 写法）或顶层 import 均可（`dispute.py` 不依赖 generator）。
2. 系统提示建议**保留** HEAD 的"state in `notes` why the finding rests on a misreading, so a human can route it as a dispute"——codex 删掉了 dispute 路径，而 dispute 正是 governance 路由的出口。
3. findings 段标题 `VERIFIED FAILURES FROM THE LAST ROUND` 会给 build.py 合成的 `[BLOCKER]` 文本（生成被拒/导出被拒/byte-identical/guard 拒绝）也戴上"verified failure"帽子；它们确实是机械拒绝，可接受；若想更准确用 `WHAT STOPPED THE LAST ROUND`。
4. `shape_work(out, task, findings)`（`_current_work`）用 findings 文本决定哪些文件保持全文；过滤后提示更窄但恰好指向要修的 DCL artifact，无害。
5. `repair_guard.py` 的正则**对文档型项目误报风险高**：`retry_or_fallback` 和 `disabled_assertion`（`skip`）会命中 Markdown 正文里的普通英文单词（CrossAudit 的主用例是 SUMMARY.md/报告）。建议：范围/行数/二进制筛查对所有文件生效，`DEFENSIVE_PATTERNS` 只对代码后缀（`.py .js .ts .sh .go .rs …`）的新增行生效；`max_changed_lines=200` 对一次重写整份 Markdown 的修复也偏紧，文档类默认放宽或按文件类型分档。
6. codex 的 `tests/test_evidence_authority.py` 中 `test_repair_guard_*` 和 `test_only_machine_blockers_are_returned_for_automatic_repair` 三个用例可原样搬到 HEAD（不依赖 `authority.decide`）。

### (e) 内核触碰：无。

---

## 6. 内核包（`auditor/ broker/ ledger/ policy/ dcl/`，additive-only）触碰汇总

| 文件 | 本簇是否触碰内核 | 说明 |
|---|---|---|
| cli/build.py | 否 | 但 `verified_only` 过滤的正确性依赖 `auditor/run.py` 让孤立模型 BLOCKER 走 ESCALATE；否则用 §2(d) 方案 B 在 build 侧兜底 |
| cli/main.py | 否 | 读 `outcome.authority`，需 `AuditOutcome` 有该字段（additive：`authority: dict = field(default_factory=dict)`）——由 A/B 簇决定 |
| console/* | 否 | |
| generator.py / repair_guard.py | 否 | |

codex 自己对 `auditor/run.py` 的改动**不是 additive**：它重写了 verdict 合成（`BLOCKED` 只来自 authority，`NON_EVIDENTIAL_PROVIDER` 的 PASS 变 ESCALATE），并改了 HEAD 的既有断言（`test_replay_provider_pass_is_marked_non_evidential` 期望 PASS；`test_three_cli_build_revisions_remain_one_cycle_and_end_escalated` 期望三轮 BLOCKED）。这与 D147（"DCL 硬失败优先于已验证的模型 verdict"）不矛盾，但把"模型 verdict 被读且被采纳"的默认行为改成了"模型 verdict 只是提案"，是产品级决策，应由拨盘控制而非默认切换。

---

## 7. 测试基线

命令（需显式 `PYTHONPATH`，否则 venv 解析到 `crossaudit_v4` 的旧包）：
```
PYTHONPATH=/Users/ericdong/Documents/Crossaudit/crossaudit_integ/src \
/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python -m pytest -q tests/ \
  -k "build or console or main or cli" -x --timeout=300 -p no:cacheprovider
```
结果：**194 passed, 1862 deselected, 0 failed, 51.32s**（`--timeout` 可用）。日志：`/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/codex-compare/pytest-C.log`。
（第一次不带 PYTHONPATH 的运行在 `tests/test_approval.py` collect 阶段 `ModuleNotFoundError: crossaudit.broker` 即停，非代码问题。）

融合后必须重跑的相关文件：`tests/test_loop_integrity.py`（含 build loop 三轮用例）、`tests/test_build_commit_secretscan.py`（guard 与 secret scan 同一插入点）、`tests/test_console_translation_boundary.py` / `test_console_strings_by_execution.py`（新文案必须有 ZH）、`tests/test_admission_and_console.py`。

---

## 8. 建议落地顺序（本簇内部）

1. `generator.py` 三处 + `repair_guard.py` + `config.py::RepairPolicy` + scaffold 模板（纯加法，先绿）。
2. `build.py`：`repair_scope`/`locally_rendered`/guard 调用（插在 `_staged_secret` 后）/`repair_refusal_used` 自愈一次/新 cause。默认 `cfg.repair.enabled` 由用户定。
3. `build.py` 方案 B 或等 A/B 簇的 `AuditOutcome.authority`，二者取一；无论哪种，模型独断 BLOCKER 是否进 governance 由配置拨盘决定，并同步改 `test_three_cli_build_revisions…`。
4. `main.py`：`_provider_stop_reason` 分支 + receipt/JSON 透传；人读输出不加 `AUTHORITY:` 独立行。
5. console：`Cycle.authority*` 字段 + `requested` 文案 + Decision Center `cause==='evidence_governance'` 分支 + ZH 条目；不改流水线 detail、不加 attempts 列。
