# Cluster A — 审计内核文件融合分析（codex `dd725d3` × v5-redesign `c170c17`）

merge-base `7ded699`。只读分析；三方合并模拟结果在
`/private/tmp/claude-501/-Users-ericdong/e8f80e28-bc0c-43ea-845e-513b702467fc/scratchpad/codex-compare/merge3/`
（`base-*` / `ours-*` / `theirs-*` / `merged-*`，`git merge-file -p` 生成，未触碰工作树）。

> 测试运行注意：`crossaudit_v4/.venv` 的 site-packages 里装了一份 **旧的** `crossaudit`
> （`.../site-packages/crossaudit/__init__.py`）。直接 `python -m pytest` 跑的是旧包
> （会看到 7 个假失败，含 advisory-only 的 ConfigDenial）。必须加
> `PYTHONPATH=/Users/ericdong/Documents/Crossaudit/crossaudit_integ/src`。
> 加上后，HEAD 上本簇相关 14 个测试文件 **193 passed**；
> `test_empty_is_not_failed.py + test_source_independence.py + test_admission_and_console.py` 83 passed。

---

## 0. 两条线对同一问题的回答

| | codex `dd725d3` | v5-redesign HEAD |
|---|---|---|
| 问题 | "audit incentives 制造 defensive programming / 两个模型互相制造审批" | 同一问题（D141–D147） |
| 手段 | **权威层**：`authority.py` 把 DCL 发现标 `verified=True`、模型发现标 `textual_judgment/verified=False`；自动 BLOCK 只允许 verified blocker 或 ≥2 producer ∧ ≥2 mechanism；孤立模型 BLOCKER → `ESCALATE`（git-governance）；receipt 加 `authority` 块；generator 只收 `DCL:` blocker；`repair_guard` 审 diff | **激励层**：允许 advisory-only constitution（D143）、generator prompt 重排（D144：fix 与 counter-evidence 平级）、`scope_started` 三态（D38/w1：空 scope 既非 pass 也非 fail → `ESCALATE`+`NOTHING_AUDITED`）、finding states（`feat/finding-states` 未合，ALLEGED/CONFIRMED…，"decide nothing with it yet"）、Observe 默认要等测出 confirmation rate 再定（D142） |
| 模型 BLOCKER 处置 | 立刻终止自动循环，round 1 就 ESCALATED（codex 自测 `test_model_blocker_stops_before_defensive_revision_loop`） | 仍走 bounded revision loop（BLOCKED → max_rounds 后 ESCALATED），generator 被告知可提交反证 |

关键张力：codex 的 `decide()` 让**每一个**模型 BLOCKER 直接变人工事件，等于把
"bounded automatic revision"（V5_KERNEL invariant 5 前半句）对语义发现整体关掉；
我们这条线（D142）明确说"降权要等 finding states 测出 confirmation rate 再决定，不能因为 reviewer 论证得好就改默认"。
codex 的 ladder 正是"argument alone 改默认"。所以 `decide()` 的**结构**（evidence plane + 可校验 authority 块）值得吸收，
但它的**默认判定**（lone model BLOCKER → ESCALATE）应做成可配置 policy，而不是无条件替换 ladder。下面每个 recipe 以此为前提。

---

## 1. `src/crossaudit/auditor/run.py`

### (a) codex 做了什么
- 删掉整个 `if/elif` ladder，改成：先算 integrity（`INVALID_REPLY`/`BOUNDS_EXCEEDED`/`NON_EVIDENTIAL_PROVIDER`），再 `records_from_audit(dcl, reply, …)` → `decide_authority(records, coverage_complete=…, integrity_errors=…, escalation_lock=…, no_model=…, auditor_requested_escalation=…, non_evidential_provider=…)`，`verdict = decision.workflow_verdict`。
- `AuditOutcome` 新增**必填**字段 `authority: dict`（无默认）。
- `render_report()` 加表格行 `| evidence authority | **STATUS** via `route` |`、`| evidence policy | … |` 和一节 `## Authority routing`（verify.py 正则绑定第一行）。
- 语义变化（相对 7ded699）：
  1. 孤立模型 BLOCKER：`BLOCKED` → `ESCALATE`。
  2. replay/NON_EVIDENTIAL 的 PASS：`PASS`+`NON_EVIDENTIAL_PROVIDER` → `ESCALATE`+`NON_EVIDENTIAL_PROVIDER`。
  3. **escalation_lock 优先级降到 DCL hard failure 之后**（`decide()` 第一分支是 `hard or consensus`）：锁定 cycle 若有 DCL 失败 → `BLOCKED` 而非 `ESCALATE`。与 run.py docstring 第 6 行 "an escalated cycle is not routed around" 相反，是真正的削弱。
  4. provider 故障 + 0 hard failure（非 wait 类）：`DCL_ONLY`+`PROVIDER_FAILURE` → `ESCALATE`+`PROVIDER_FAILURE`。
  5. `bounded` 时无条件 `integrity="BOUNDS_EXCEEDED"`（会覆盖 `PROVIDER_FAILURE`）；HEAD 只在 ladder 到该分支才设。
  6. `no_model = reply is None and not invalid and not provider_failure` → `DCL_ONLY`，与 HEAD offline 路径一致。

### (b) 我们做了什么（7ded699→HEAD，+21/-2）
- `run_checks(..., context=ctx)`：`source_provenance` 开启时构造 `CheckContext(governed_source_ids=…)`。
- `prompt_mod.build(..., tool_evidence=evidence_view(cfg))`。
- ladder 在 `total_hard_failures > 0` 之后、`invalid` 之前插入 `elif not dcl.get("scope_started", True): verdict="ESCALATE"; integrity=… or "NOTHING_AUDITED"`（"THE WEAKENING GUARD"）。
- 未合的 `feat/finding-states`（落后 HEAD 24 commit）会加 `finding_states(dcl, model_reply)`（DCL→CONFIRMED，model→ALLEGED），不改 ladder。

### HEAD 能产生的全部 integrity 值 → codex 映射覆盖检查
`grep "integrity =" src/crossaudit/auditor/run.py`（HEAD 行号）：`OK`(177)、`PROVIDER_FAILURE`(232)、`NOTHING_AUDITED`(248)、`INVALID_REPLY`(251)、`BOUNDS_EXCEEDED`(254)、`NON_EVIDENTIAL_PROVIDER`(265)。
`receipt/schema.py` 对 `audit_integrity` **只要求存在**（`REQUIRED_AUDIT`），无词表；`VERDICTS = ("PASS","BLOCKED","ESCALATE","DCL_ONLY")` 与 codex `workflow_verdict` 集合一致，`validate_block.expected` 也只用这四个。

| HEAD 路径 | HEAD verdict/integrity | codex `decide()` | 覆盖？ |
|---|---|---|---|
| escalation_lock | ESCALATE | ESCALATE，**但有 DCL blocker 时 → BLOCKED** | 部分——优先级反了 |
| DCL hard failure | BLOCKED | BLOCK/BLOCKED | ✔ |
| `scope_started=False` | ESCALATE / NOTHING_AUDITED | **无对应参数**：0 finding + reply PASS → `PASS`；offline → `DCL_ONLY` | ✘ **丢失**（空目录又能 PASS，w1 说的 "the one outcome worse"） |
| invalid reply | ESCALATE / INVALID_REPLY | ESCALATE | ✔ |
| bounded | ESCALATE / BOUNDS_EXCEEDED | ESCALATE | ✔（integrity 覆盖顺序略异） |
| reply PASS | PASS | PASS 或 ADVISORY→PASS | ✔ |
| reply PASS via replay | PASS / NON_EVIDENTIAL_PROVIDER | ESCALATE / NON_EVIDENTIAL_PROVIDER | 变了 |
| reply ESCALATE | ESCALATE | ESCALATE | ✔ |
| reply BLOCKED（模型） | BLOCKED | ESCALATE | 变了（核心分歧） |
| offline / no reply | DCL_ONLY | DCL_ONLY | ✔ |
| provider failure, 0 hard | DCL_ONLY / PROVIDER_FAILURE | ESCALATE / PROVIDER_FAILURE | 变了（更严；HEAD 测试只断言 integrity） |
| provider failure, ≥1 hard | BLOCKED / PROVIDER_FAILURE | BLOCKED / PROVIDER_FAILURE | ✔（`test_run_liveness_adversarial.py:221`） |

结论：`decide()` **必须**新增 `scope_started: bool = True`（或 `nothing_audited`）参数，且 escalation_lock 分支放回 `hard or consensus` 之前。

### 硬约束：源码文本测试
`tests/test_empty_is_not_failed.py::test_an_unstarted_scope_cannot_reach_pass_through_the_audit_either`
用 `inspect.getsource(run_mod)` 找字面量 `'if escalation_lock:'`，取到下一空行为止，断言其中含 `scope_started` 且在 `"PASS"` 之前。
codex 删了 `if escalation_lock:` → `ValueError` → 红。融合后 run.py **必须保留以 `if escalation_lock:` 开头、含 `scope_started` 的 ladder 段落**。

### (c) 冲突类型：**冲突**（同一 hunk `@@ -225,35`；`git apply --check` 失败；3-way 在 merged-run.py 254–276 留冲突块）

### (d) 融合配方
保留 HEAD 的 if/elif ladder 作为 "workflow ladder"，把 codex 的 `decide()` 作为第二阶段，只在"模型有话说"的分支覆盖：

```python
# 1. 前置 integrity 保持 HEAD 优先级（不用 codex 的无条件赋值）
# 2. ladder —— 字面量 `if escalation_lock:` 必须保留
if escalation_lock:
    verdict = "ESCALATE"
elif dcl["total_hard_failures"] > 0:
    verdict = "BLOCKED"
elif not dcl.get("scope_started", True):        # 保留 HEAD 241-248 整段
    verdict = "ESCALATE"
    integrity = integrity if integrity != "OK" else "NOTHING_AUDITED"
elif invalid:
    verdict = "ESCALATE"; integrity = integrity if integrity != "OK" else "INVALID_REPLY"
elif bounded:
    verdict = "ESCALATE"; integrity = "BOUNDS_EXCEEDED"
elif reply:
    verdict = reply["verdict"]; model_decided = True
else:
    verdict = "DCL_ONLY"
if actual.provider in NON_EVIDENTIAL and verdict == "PASS":
    integrity = "NON_EVIDENTIAL_PROVIDER"

# 3. 证据权威层：记录 + 可选降权，不重算已决定的 ESCALATE/BLOCKED/DCL_ONLY
records = records_from_audit(dcl, reply, provider=…, model=…, vendor=…)
decision = decide_authority(
    records, coverage_complete=…, integrity_errors=[…同 codex…],
    escalation_lock=escalation_lock,
    scope_started=dcl.get("scope_started", True),            # 新参数
    no_model=…, auditor_requested_escalation=…, non_evidential_provider=…,
    model_blocker_policy=cfg.authority.lone_model_blocker)   # 新参数: "block"(=HEAD) | "escalate"(=codex)
# 4. 只有 ladder 落在"模型自己的 verdict"这一支时才让 decision 覆盖
if model_decided and decision.workflow_verdict != verdict:
    verdict = decision.workflow_verdict
authority = decision.as_dict()
```

需改 `authority.py`（新文件无冲突，但要补）：
- `decide(..., scope_started=True, model_blocker_policy="block")`：`scope_started=False` → `("ESCALATE","ESCALATE","git-governance",True)`，放 `escalation_lock` 之后、`no_model` 之前；`escalation_lock` 分支移到 `hard or consensus` **之前**；`unresolved` 分支按 policy：`escalate` → 现状；`block` → `("BLOCK","BLOCKED","bounded-revision",False)`，`blocking_evidence_ids` 为空、rationale 写明 "provisional: textual judgment admitted to the bounded revision loop by policy"。receipt 仍诚实记录"模型 blocker 未验证"，产品行为不变。
- `validate_block()` 的 `expected` 表不用改；`POLICY_VERSION` 检查改成已知版本集合（§2）。
- 与 `feat/finding-states` 对齐：`EvidenceRecord.verified` 与 `state`（CONFIRMED/ALLEGED）是同一事实两种命名；`records_from_audit` 读 `finding.get("state")`，模型行写 `ALLEGED`。

`AuditOutcome.authority` 改 `field(default_factory=dict)`——`tests/test_committed_audit_bytes.py:41` 手工构造 `AuditOutcome(...)` 无此字段，必填会 `TypeError`。

其他 codex hunk：import 两行、`render_report(authority=…)` 表格行 + `## Authority routing` 段、`AuditOutcome` 传参——可直接吸收。docstring 改为 "lone model BLOCKER → policy (default: bounded revision, recorded as unverified)"，并补 "unstarted scope → ESCALATE (NOTHING_AUDITED)"。

### (e) 内核风险
- 按 codex 原样合：**违反 never weakened** 两处——escalation_lock 优先级下降；`scope_started` 分支丢失导致空 scope 可 PASS。
- 按配方合：只增加 receipt 字段和 ESCALATE 来源；无路径从非 PASS 变 PASS；`DCL_ONLY`/`NOTHING_AUDITED`/`BOUNDS_EXCEEDED` 全保留。

---

## 2. `src/crossaudit/receipt/build.py` + `receipt/schema.py`（含 `verify.py`）

### (a) codex
- `build(..., authority: dict | None = None)`，末尾 `if authority is not None: receipt["authority"] = authority`。
- `schema.validate()` 末尾：`authority` 可选；存在时 `validate_block()`（必需键、`policy_version == POLICY_VERSION`、status 词表、`evidence_digest` 重算、status↔verdict 映射）+ `authority.workflow_verdict == audit.verdict`。
- `verify.py`：正则绑定 report 的 `| evidence authority | **X** via `route` |`；`status ∉ {PASS, ADVISORY}` 进 `admission_shortfalls`；`admit()` 同样拒绝。
- **无 schema bump**：`RECEIPT_SCHEMA = 2` 在 base/codex/HEAD 三处均为 2。

### (b) 我们
- `build.py`(+97)：`_tool_evidence()` 三态（absent/intact/broken，broken → `IntegrityDenial`）；末尾按"存在才写"追加 `tool_evidence`、`reproduction`、`sources`；`cycle.constitution_commit`（D36）。
- `schema.py`(+52)：`validate()` 末尾按"存在才校验"追加三块；`sources` 必须伴随 `tool_evidence`。
- `verify.py`(+435)：re-derive 各块；`| verdict | **X** |` 正则未变。
- 也**没 bump**（三块都注明 "no schema bump, byte-identical when absent"）。

### 版本号是否冲突？
不冲突：双方都没动 `RECEIPT_SCHEMA`，都采用 "optional block, absent ⇒ byte-identical" 惯例；`authority` 是第四块。`digest() = sha256(canonical(receipt))` 全字典排序序列化，旧 receipt 无 `authority` 键 → digest 不变 → 旧 receipt 继续可验证。

### 会否打破我们的 verify 测试？
- 只加 `authority` 参数（默认 None）：HEAD 所有 `build(...)` 调用点不传 → 字节不变 → 193 个测试不受影响。
- `cli/main.py` 两处 `build(..., authority=outcome.authority)`（codex 非本簇 hunk）合入后每个新 receipt 带 `authority`，`verify()` 就要求 report 有 `evidence authority` 行——`render_report` 同步合即可。`_receipt_for()`（`tests/test_loop_integrity.py:63`）等 helper 用 `outcome.report` 写 report 再 `build()`，一致。
- 真正的兼容陷阱：`validate_block` 的 `policy_version != POLICY_VERSION` 硬相等——policy 升 v2 后所有 v1 receipt 在 `schema.validate()` 直接 `IntegrityDenial`，违反 "older receipts stay verifiable"。改成 `KNOWN_POLICY_VERSIONS` 集合，verify 里把"旧策略"记为 shortfall 而非拒绝。
- `from ..authority import validate_block` 是延迟 import，无循环依赖。

### (c) 冲突类型：**互补**（3-way 在两文件各一个"同处追加"冲突，纯文本相邻，无语义交叉；verify.py 三个 hunk `git apply --check` 干净）

### (d) 配方
- `build.py`：codex 的 `if authority: receipt["authority"] = authority`（用真值而非 `is not None`，因为 `AuditOutcome.authority` 默认空 dict）放在我们 `sources` 块之后、`return receipt` 前；签名加 `authority: dict | None = None`。我们已把 `return {…}` 改为 `receipt = {…}`，codex 那行重复，取我们的。
- `schema.py`：codex authority 校验段接在我们 `sources` 段之后（HEAD 第 143 行 `return raw` 前）。
- `verify.py`：直接 apply（行号漂到 446/467/553 附近）。
- 建议补：`validate_block` 校验 `blocking_evidence_ids ⊆ evidence ids`（codex 未做，digest 覆盖不到的语义洞）。

### (e) 风险
- 追加可选块 = 额外证据，符合 additive；老 receipt 字节/digest 不变。
- 唯一削弱风险是 `policy_version` 硬相等（已给修法）。

---

## 3. `src/crossaudit/config.py`

### (a) codex：`_ALLOWED_TOP` 加 `"repair"`；新 `RepairPolicy(enabled=True, max_changed_lines=200)`；`load()` 校验 `repair` 段（1–10000）；`Config.repair` 字段。
### (b) 我们：`_ALLOWED_GENERATOR = _ALLOWED_ROLE | {"streaming"}`、`generator_streaming`、`find()` i18n 错误、`checks:` 改为 profile 解析（`dcl/profiles.resolve`；general/science/off）。
### (c) 冲突类型：**互补 / 可直接吸收**。`git apply --check` 因 `_ALLOWED_TOP` 上下文漂移失败，但 `--3way` 与 `git merge-file` 均**零冲突**（`merged-config.py` 无标记）。
### (d) 配方
- 三方合并直接得正确结果；人工确认 `Config(...)` 构造末尾同时有 `generator_streaming=…` 和 `repair=repair`。
- 建议把段改为 `authority:`（`lone_model_blocker: block|escalate`，`repair: {enabled, max_changed_lines}`），让 §1 的 policy 开关和 codex 的 repair budget 同段。至少加 `authority.lone_model_blocker` 默认 `block`（= HEAD 行为），使 codex 语义成为 opt-in dial——与 "strictness is an opt-in dial" 定位一致。
- `repair.enabled` 在 HEAD 只被 codex 的 `cli/build.py` hunk 消费（非本簇）；单独合 config 无行为变化。
### (e) 风险：无（纯新增键，未知键仍拒绝）。

---

## 4. `src/crossaudit/scaffold/__init__.py`

### (a) codex：模板 `checks: [{checks}]` 后追加注释 + `repair:\n  enabled: true\n  max_changed_lines: 200`。
### (b) 我们：0 行改动（HEAD == base）。
### (c) 冲突类型：**可直接吸收**（`git apply --check` 通过）。
### (d) 配方
- 直接 apply，但**顺序依赖**：必须在 config.py 认识 `repair` 键之后，否则 `crossaudit init` 生成的 yml 被 `load()` 以 "unknown keys ['repair']" 拒绝——任何 init→load 测试立刻红。
- 若按 §3 改成 `authority:` 段，模板同步。
- 我们的 `checks: [{checks}]` 现在填 profile 名，codex hunk 不碰该行，兼容。
### (e) 风险：无。

---

## 5. `tests/test_loop_integrity.py`

### (a) codex 改了 4 处
1. `_receipt_for()` 传 `authority=outcome.authority`。
2. `test_replay_provider_pass_is_marked_non_evidential`：`verdict == "PASS"` → `"ESCALATE"`，加 `authority["route"] == "git-governance"`。
3. 新增 `test_single_model_blocker_routes_to_governance`。
4. **删除** `test_three_cli_build_revisions_remain_one_cycle_and_end_escalated`（三轮 BLOCKED→ESCALATED），换成 `test_model_blocker_stops_before_defensive_revision_loop`（round 1 即 `EXIT_ESCALATED`）。

### (b) 我们改 3 处（文件后半，与 codex 不重叠；`git apply --check` 干净）
- `test_build_duplicate_revision_reports_the_actual_escalation_reason`：no-progress 自愈 → round 3、`escalation_cause == "no_progress"`。
- `test_weakened_constitution_is_refused` → `test_working_tree_constitution_drift_does_not_change_pinned_receipt`。
- `test_transient_failure_does_not_spend_the_revision_budget`：verdict 后同 sha 不再 advance（D36）。

### HEAD 实际行为（193 passed）与 codex 期望的矛盾
| 测试 | HEAD | codex |
|---|---|---|
| `test_replay_provider_pass_is_marked_non_evidential` (L183) | verdict **PASS** + integrity NON_EVIDENTIAL_PROVIDER（拒绝发生在 verify/admit） | verdict **ESCALATE** |
| `test_three_cli_build_revisions_remain_one_cycle_and_end_escalated` (L255) | 模型 BLOCKED 三轮：r1、r2 `EXIT_BLOCKED`，r3 `EXIT_ESCALATED` | 删除；r1 即 ESCALATED |
| `test_build_loop_itself_passes_the_cycle_through_all_three_rounds` (L289) | 三轮走完（无 reply，靠 DCL 失败）——不受影响 | 未改 |
| `tests/test_advisory_only_constitution.py::test_an_advisory_only_constitution_still_passes_clean_work` | replay PASS，**无** `evidential` fixture，断言 `PASS` | codex 的 non_evidential→ESCALATE 会让它红 |
| `tests/test_source_independence.py:207` | 用 `evidential` → PASS | 不受影响 |
| `tests/test_empty_is_not_failed.py`（源码文本） | 需要 `if escalation_lock:` 段内有 `scope_started` | codex 删该字面量 → 红 |
| `tests/test_committed_audit_bytes.py:41` | 手工 `AuditOutcome(...)` 无 `authority` | codex 必填 → `TypeError` |

### (c) 冲突类型：**冲突（语义）**，文本可直接 apply。

### (d) 配方
- 保留 HEAD 的三轮测试作为 `lone_model_blocker: block`（默认）合同；codex 的两个新测试改成开启 `lone_model_blocker: escalate` 的参数化版本。
- `test_replay_provider_pass…`：保留 HEAD 断言。注意 `validate_block` 要求 `status ESCALATE ⇒ verdict ∈ {ESCALATE, DCL_ONLY}`，所以保留 verdict PASS 时 `decide()` 的 `non_evidential_provider` 不应触发 ESCALATE，改为 status `ADVISORY`、route `not-admissible`；verify/admit 本就靠 `audit_integrity != OK` 拒绝，双保险已在。
- `_receipt_for()` 的 `authority=outcome.authority` 可合（`build()` 用 `if authority:`，否则空 dict 写成非法块）。
- `tests/test_evidence_authority.py`（codex 新文件）直接吸收；`test_one_model_blocker_is_a_governance_case_not_an_automatic_patch` 改为显式 `model_blocker_policy="escalate"`。

### (e) 风险：测试层无内核风险；但删除三轮测试 = 删除 bounded-revision 的回归保护，不应接受。

---

## 6. codex 对 `auditor/run.py` 的改动是否符合 "additive only, never weakened"？

**正方**：每处改变都把结果推向更保守——模型 BLOCKER 自动返工→人工；replay PASS→ESCALATE；provider 故障 DCL_ONLY→ESCALATE。无路径新增 PASS。receipt 多一个可校验块，verify 多三道检查。从 fail-closed 角度是加严。

**反方**：
1. `escalation_lock` 优先级放到 DCL blocker 之后：人工锁定的 cycle 可由 DCL 失败"决定"为 BLOCKED，HEAD 的规则是锁定优先。直接削弱。
2. 丢掉 `scope_started` 分支（重写 ladder 时 base 尚无它），空 scope 可 PASS——w1 标为最坏结果。
3. "never weakened" 的另一半是 **backward compatible**：`AuditOutcome.authority` 必填、`policy_version` 硬相等、删除三轮回归测试、把 bounded automatic revision 对语义发现整体关闭——都是改合同而非叠加。
4. D142：把"模型 BLOCKER 不能自动 block"作为**默认**，正是 owner 明确拒绝的"仅凭论证改默认"。

**裁定**：codex 的**证据层**（`authority.py` + receipt `authority` 块 + verify 绑定）是 additive 的，可吸收；
**对 ladder 的替换不是 additive 的**——需 (i) escalation_lock 放回最前、(ii) 加 `scope_started`、
(iii) lone-model-BLOCKER→ESCALATE 做成默认关闭的策略开关、(iv) `authority` 字段/参数全可选。四点做到后才满足内核规则。

---

## 7. 本簇融合步骤（按依赖与风险排序）

1. **新文件先进**：`src/crossaudit/authority.py`、`tests/test_evidence_authority.py`（`git apply` 干净）。随即修改 `authority.py`：`decide()` 加 `scope_started`、`model_blocker_policy`；escalation_lock 提前到第一分支；`non_evidential_provider` 改 ADVISORY 路线；`validate_block` 用已知版本集合；校验 `blocking_evidence_ids ⊆ evidence`。
2. **config.py**：三方合并（零冲突），加 `authority.lone_model_blocker`（默认 `block`）与 `repair` 段。
3. **auditor/run.py**：按 §1(d) 手写——保留 HEAD ladder 原文（含 `if escalation_lock:` 与 `scope_started` 段），在 `reply` 分支后叠加 `decide_authority`；`AuditOutcome.authority` 给默认值；`render_report` 加两行 + 一节。
4. **scaffold/__init__.py** 模板 hunk（config 已认识新键后）。
5. **receipt/schema.py → build.py → verify.py**：三段可选块追加（verify 干净 apply；build 用 `if authority:`）。
6. **tests/test_loop_integrity.py**：apply codex 文本 hunk 后，回滚"删除三轮测试"、两个新测试参数化到 `escalate` 策略、`test_replay_provider_pass…` 保持 HEAD 断言。
7. 与 `feat/finding-states` 的对齐（`verified` ↔ `state`）在该分支合入时处理；本簇不阻塞。

## 8. 必须全绿的命令（带 PYTHONPATH，否则跑的是 site-packages 旧包）

```sh
export PYTHONPATH=/Users/ericdong/Documents/Crossaudit/crossaudit_integ/src
PY=/Users/ericdong/Documents/Crossaudit/crossaudit_v4/.venv/bin/python
$PY -c 'import crossaudit; assert "crossaudit_integ/src" in crossaudit.__file__, crossaudit.__file__'

$PY -m pytest -q -p no:cacheprovider \
  tests/test_loop_integrity.py tests/test_advisory_only_constitution.py \
  tests/test_empty_is_not_failed.py tests/test_evidence_authority.py \
  tests/test_committed_audit_bytes.py tests/test_cycle_integrity.py tests/test_cycle_binding.py \
  tests/test_receipt_evidence_fail_closed.py tests/test_receipt_tool_evidence.py \
  tests/test_receipt_sources.py tests/test_verifier_rederives_remaining.py \
  tests/test_enterprise_receipt_tamper.py tests/test_receipt_documents.py \
  tests/test_reproduction_bundle.py tests/test_stability_slice_b.py \
  tests/test_run_liveness_adversarial.py tests/test_source_independence.py \
  tests/test_admission_and_console.py tests/test_local_demo.py
```
基线（HEAD 未融合）：前 14 个文件 193 passed；`test_empty_is_not_failed + test_source_independence + test_admission_and_console` 83 passed。融合后只能增不能减。

建议新增两条 guard 测试：
- 空 scope + reply PASS 真跑 `run_audit` → verdict ≠ PASS，integrity `NOTHING_AUDITED`（现有测试只查源码文本）。
- `escalation_lock=True` + DCL hard failure → verdict `ESCALATE`（HEAD 语义；codex 会给 BLOCKED；目前无测试直接断言）。
