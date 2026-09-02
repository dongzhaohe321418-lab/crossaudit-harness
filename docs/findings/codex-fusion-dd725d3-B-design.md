# Report B — 设计/概念对比:codex `evidence-governance-fusion` (dd725d3) vs 我们的 `v5-redesign` (c170c17)

merge-base `7ded699`。只读分析;未改任何 tracked 文件。所有 `file:line` 引用:codex 侧以 `dd725d3:` 前缀,我们侧无前缀(HEAD c170c17);决策编号来自 `docs/DECISIONS.md`。

---

## 0. 一句话结论

codex 那条线用**一条准入策略**(`authority.py`)加**一个修复守卫**(`repair_guard.py`)回答"模型单方 BLOCKER 不能自动变成修复指令";我们这条线用**去激励**(D141–D147:允许只咨询的宪法、finding 状态、prompt 侧重、仪表盘诚实、申诉独立)回答同一个问题。两者**方向一致、机制互补、但在三个具体点上冲突**:

1. codex 把"模型单方 BLOCKER → 第一轮就 ESCALATE 给人"设为**不可配置的默认**,这正是 D142 明确拒绝"仅凭论证就采纳"的 Observe-默认,且删掉了 North Star §14/§37 与 V5 不变量 5 的"有界自动修订"。
2. codex 的 `decide()` 把 hard BLOCK 排在 `escalation_lock` **之前**,回退了 `run.py:6` "an escalated cycle is not routed around" 与 `controller/state.py:215-226` 的锁语义。
3. codex 的证据词汇(`verified: bool`、ad-hoc `mechanism_family` 字符串)与 `feat/finding-states` 的六态是**同一条轴**,但 codex 把记录**绑进回执摘要**,finding-states 刻意用 sidecar 不入回执;两者都保住了旧回执可验,但只能选一种落点。

推荐:**不要原样嫁接;把 authority 的可保留性质用我们的词汇重述**(见 §4)。可近乎原样吸收的只有:回执 `authority` 块 + `validate_block` 摘要绑定 + `verify.py` 报告行绑定 + 摘要突变测试;RepairGuard 作为独立切片、修正正则后再议。

---

## 1. 逐文件对比

### 1.1 `src/crossaudit/authority.py`(codex 新增,254 行)

**codex 做了什么。** 一个纯函数策略层:

- `EvidenceRecord`(`evidence_id, finding_key, severity, evidence_type, claim, artifact, producer_id, mechanism_family, verified, verification_reason`),`evidence_id = "ev-" + sha256(canonical(payload))[:16]`。
- `records_from_audit(dcl, model_reply, provider, model, vendor)`:DCL finding → `producer_id="checker:{check}"`, `mechanism_family="deterministic:{check}"`, `verified=True`, `evidence_type` = BLOCKER→`deterministic_failure` / 否则 `reproducible_observation`;模型 finding → `producer_id="auditor:{vendor}/{provider}:{model}"`, `mechanism_family="model-semantic-review"`, `verified=False`, `evidence_type="textual_judgment"`。
- `decide(records, coverage_complete, integrity_errors, escalation_lock, no_model, auditor_requested_escalation, non_evidential_provider)` 的判定阶梯(按源码顺序):
  1. `hard`(verified ∧ BLOCKER ∧ evidence_type ∈ `HARD_EVIDENCE`)或 `consensus`(同 `finding_key` 下 ≥2 `producer_id` ∧ ≥2 `mechanism_family`,且都 verified BLOCKER)→ `BLOCK / BLOCKED / automatic-repair`
  2. `escalation_lock` → `ESCALATE / ESCALATE / git-governance`
  3. `no_model` → `ESCALATE / DCL_ONLY / obtain-audit`
  4. `errors ∨ ¬coverage_complete ∨ non_evidential_provider` → `ESCALATE / ESCALATE / git-governance`
  5. `auditor_requested_escalation` → 同上
  6. `unresolved`(BLOCKER 但既非 hard 也非 consensus,即模型单方 BLOCKER)→ `ESCALATE / ESCALATE / git-governance`
  7. 有记录但无 BLOCKER → `ADVISORY / PASS / admission`
  8. 空 → `PASS / PASS / admission`
- `validate_block(raw)`:必需键、`policy_version == "crossaudit-evidence-authority-v1"`、`status ∈ STATUSES`、`evidence_digest` 重算、status↔workflow_verdict 映射表。

**我们有什么。** 判定阶梯在 `auditor/run.py:237-265`,代码即裁决(I4),顺序是 `escalation_lock → DCL hard → ¬scope_started(NOTHING_AUDITED) → invalid → bounded → reply["verdict"] → DCL_ONLY`,末尾 `NON_EVIDENTIAL` 只打 integrity 标记不改 verdict。没有"证据记录"对象;finding 的来源只隐含在 `dcl.findings[].check` 与 `audit.{provider,model,vendor}` 里。`feat/finding-states`(未合)给 finding 加 `state`(`alleged|confirmed|fixed|withdrawn|overridden|unresolved`)和 `tier`(`deterministic|model`),写到 `cycles/<id>/findings.json` sidecar,**明确不入回执、不参与裁决**(`tests/test_finding_states.py::test_nothing_gates_on_the_new_field`)。

**关系:部分互补 + 两处冲突 + 一处已覆盖。**

| codex 性质 | 我们侧 | 关系 |
|---|---|---|
| DCL BLOCKER 自动 BLOCK,模型不能豁免 | `run.py:239-240`;D143/D147 已证明并有守卫(`test_the_deterministic_floor_still_blocks_without_any_blocker_rule`) | 已覆盖 |
| 每条 finding 有 producer / 是否已验证 | finding-states 的 `tier` + `state`(`confirmed` ≡ `verified=True`,`alleged` ≡ `verified=False`) | 同轴,finding-states 更一般(六态生命周期 vs 布尔快照) |
| 证据集摘要绑定进回执 | 回执无 findings(`receipt/build.py`);finding-states 守卫 `test_the_state_never_reaches_a_receipt_or_its_digest` 断言 `"findings" not in receipt/build.py` | **冲突(落点)**:codex 块是可选键,旧回执照样验;但与 finding-states 的 sidecar 决定二选一 |
| 模型单方 BLOCKER → 第一轮 ESCALATE,不再自动修订 | North Star §14/§37、`docs/V5_KERNEL_ARCHITECTURE.md` 不变量 5"Automatic revision is bounded"、PRODUCT_VISION §2 "ordinary post-audit revision" 属于 Decide automatically;D142 "Observe 不因论证成为默认,先量确认率" | **冲突(产品与决策顺序)** |
| `escalation_lock` 优先级 | `run.py:6,237-238`:锁最先;`controller/state.py:215-226` `blocked_by_escalation` | **冲突(codex 把 hard BLOCK 放在锁前 = 回退)** |
| `NON_EVIDENTIAL` 回放 provider 的 PASS → ESCALATE | 我们:verdict 保持 PASS,`integrity=NON_EVIDENTIAL_PROVIDER`,`admit()` 拒绝;`tests/test_loop_integrity.py:187` 断言 `verdict == "PASS"` | 冲突(fixture 语义);我们 332 个提交里大量 console/回放测试建立在"回放 PASS 走完流程"上 |
| `¬scope_started → NOTHING_AUDITED` | 我们线上新增(`run.py:241-248`,commit 7630592) | codex `decide()` 没有这个输入;原样替换 run.py 阶梯会**丢掉**它 |
| 消费者(consensus)路径 | 无 | 生产中不可达(见 Q2) |

**融合配方(见 §4)**:保留 `EvidenceRecord`/摘要绑定的**形状**,字段改用我们的词(`tier`、`state`、`check`、`route`),`decide` 在 v1 里**只派生 status,不改 verdict**,verdict 继续由 `run.py` 现有阶梯产出;`escalation_lock` 保持最先;新增 `scope_started` 输入。

### 1.2 `tests/test_evidence_authority.py`(codex 新增)

钉住 8 条性质:

1. 注册检查器的 BLOCKER 有阻断权(offline、`no_model=True` 仍 BLOCK)。
2. 单一模型 BLOCKER → ESCALATE / git-governance,`blocking_evidence_ids` 为空。
3. 两个模型、同一 `mechanism_family="model-review"` 不能制造 consensus。
4. 不同 producer + 不同 mechanism 可以 corroborate → BLOCK。
5. `as_dict()` 后篡改 `evidence[0].claim` → `validate_block` 报 digest mismatch。
6. `RepairGuard` 拒绝越界文件 + `broad_exception`/`silent_pass`。
7. 本地渲染的二进制(`report.pdf`)在 `locally_rendered_files` 里可放行。
8. `render_findings(report, verified_only=True)` 只回传 `DCL:` 前缀 BLOCKER。

**评价**:(1)(5) 直接对应我们已有或想要的性质(D147 floor;D131/D132 "ledger first, verdict second" 要求回执说明裁决依据),可近乎原样吸收(改导入路径与字段名)。(3)(4) 钉的是生产不可达路径(Q2)。(2)(8) 钉的是**尚未裁定**的产品行为(Q1)。(6)(7) 钉的是 RepairGuard,其正则会误伤(见 1.6)。测试用 `evidence_type="documentary"` 构造 verified BLOCKER 来触发 consensus——这个值不在 `HARD_EVIDENCE` 里,也不由 `records_from_audit` 生成,进一步说明该路径只有测试 fixture 能到。

### 1.3 `docs/EVIDENCE_GOVERNANCE_FUSION.md`(codex 新增,116 行)

**仍然成立(嫁接后)**:"untrusted proposal plane / trusted admission plane"的分层;工作流映射表(`PASS/ADVISORY→PASS`, `BLOCK→BLOCKED`, `ESCALATE→ESCALATE|DCL_ONLY`)与我们 `receipt/schema.py:33 VERDICTS` 完全对齐;"Confidence scores and vendor names are metadata, not proof";TCB 段落(注册检查、策略、验证器、controller、本地渲染器在 TCB 内)与 `admission.py`、`dcl/framework.py` 一致;"Older schema-v2 receipts remain verifiable"。

**需要改写**:

- "Evidence Lab supplies the evidence vocabulary" — 我们仓库没有 Evidence Lab 这个架构;来源应改为 D141–D147 + finding-states。
- "Admission rule" 第 2 条(≥2 producers ∧ ≥2 mechanism families)在生产不可达,写成"现行规则"是 D141(`sealed`)/D146(guard 名超出其覆盖)同一类问题:**名字宣称代码没有的能力**。应降级为"未来策略版本的扩展点"或删掉。
- "Only verified machine blockers are returned to the Generator automatically" — 与 D144 裁定("reorder the emphasis; do not add capability";保留 counter-evidence 通道)相冲;且 ADVISORY 模型 finding 也不再回传生成端,违反 North Star §12 "Findings carry … recommended correction"。
- "Workflow mapping" 行 "missing model coverage → DCL_ONLY → obtain a semantic audit" 成立;但需补 `NOTHING_AUDITED`(我们线新增)。
- "Code map":`crossaudit.authority` → 建议 `crossaudit.auditor.authority`(Q3);`crossaudit.repair_guard` 若采纳应放顶层或 `cli/` 侧的独立模块,不进内核五包。
- "admission" 这个路由名与我们 `admission.py`(部署档位 local/remote/paired/enforced)和 `receipt/verify.admit()` 三义;改名(如 `route="receipt"`)。

### 1.4 `DESIGN.md` diff(codex +30;我们自 base **未改** → 补丁可干净套用)

codex 把分层图从三层改为四层,在"两个 agent"与"引擎"之间插入 "证据准入 + CrossAudit 治理:DCL · authority · repair guard · disputes",并把 `auditor (judges)` 改成 `auditor (proposes)`,新增 §7.1 "证据先于权限"。

**关系:可吸收,但措辞要对齐我们的决策语言。** "auditor proposes" 与 D141 "model findings are contestable evidence" 一致;但 §7.1 "单一模型 BLOCKER 自动进入 Git 治理" 是 Q1 未裁定行为,不能写成已定;"只有经过验证的 machine blocker 会自动返回 Generator" 与 D144 冲。另注意 `DESIGN.md` 是协议语义的最高权威(NORTH_STAR 前言 "protocol semantics in DESIGN.md still govern"),所以这段一旦写入就是**协议变更**,须先有决策记录(D148+)再改文档。

### 1.5 `README.md` diff(双方都改;hunks 不重叠)

- **我们**:4.14.0→4.15.0;新增 "Signed, externally verifiable receipts"(Ed25519/DSSE、`export-pubkey`、`--pubkey`)、"Reproducibility bundle"(`crossaudit reproduce`)、"How strict the deterministic layer is (a dial, not the identity)"(`checks:` profiles `off/general/science/research`)、`CROSSAUDIT_SIGNING_KEYFILE`、命令表三行。
- **codex**:流程图改为 "evidence gate → verified BLOCK / clean PASS / uncertain claim → Git governance";功能清单加两条;状态表 `BLOCKED`/`ESCALATED` 释义改写;新增 "Only verified machine blockers are returned…" 段落;`repair:` 配置块。

**关系:文本可机械合并(无重叠 hunk);语义上 codex 的三处改动都是 Q1 行为的对外承诺**——只在行为被采纳后才可写进 README。我们线的 "a dial, not the identity" 段落恰好提供了 codex 规则该有的形态:**一个 opt-in 档位而非身份**。

### 1.6 `src/crossaudit/repair_guard.py`(codex 新增,110 行)

**codex 做了什么**:解析 `git diff --cached --binary`,拒绝:越界文件、>`max_changed_lines`(默认 200)、`DEFENSIVE_PATTERNS`(`broad_exception`, `silent_pass`, `retry_or_fallback`, `suppression`, `disabled_assertion`)、非本地渲染的二进制。`cli/build.py` 在 BLOCKED 后的下一轮 `git restore --staged` 并把拒绝理由作为 `[BLOCKER]` 回传生成端;`config.py` 新增 `RepairPolicy`;`scaffold` 模板加 `repair:` 块。

**我们有什么**:**没有等价物**。`grep -rn "guard|defensive|budget" src/` 只命中 usage guardrail(`usage.py:315`,`errors.py:206`)、gitio 文档大小 guard、document_export 解压炸弹 guard。D144 处理的是 prompt 侧"训练防御性编程"的指控,裁定"reorder emphasis, do not add capability"——那是 prompt 层,与 diff 层守卫**不互斥**。

**关系:互补,填补空白;但按我们的守卫纪律(D10/D121/D64)现状不能合:**

- `retry_or_fallback = (?i)\b(retry|retries|fallback|best[_ -]?effort)\b` 与 `disabled_assertion = (?i)\b(skip|xfail)\b` 对**散文**同样生效。我们的生成端主要产出 Markdown/报告(PRODUCT_VISION §4,North Star §37 的 1500 字 PDF 报告);一份讨论 provider fallback 的报告、一句 "skip the introduction" 都会被判 defensive → D121 "a guard that reddens on correct code is as much a defect"。守卫必须按文件类型(代码 vs 文档)分域。
- 只在 `repair_scope is not None` 的修复轮生效,且 `repair_scope` 仅由 `DCL:` 规则的 artifact 推导(`dd725d3:cli/build.py:466-471`);模型 BLOCKER 已被 ESCALATE 掉,所以守卫在 codex 设计里**只约束 DCL 失败后的修复**——范围比其文档宣称的窄。
- `git restore --staged -- *staged` 后 `continue` 进入下一轮,但没有重新走 `document_export.render_export`;若被拒的是渲染产物这轮的 `locally_rendered` 集合会过期。需要在我们的 `build.py`(自 base +774 行,含 usage guardrail 停机、format repair、document integrity)里重新定位插入点,不是 patch 套用。

**融合配方**:独立切片 `feat/repair-guard`,放在 `src/crossaudit/repair_guard.py`(非内核五包);规则分域(代码后缀才跑 `DEFENSIVE_PATTERNS`;文档只跑越界/预算/二进制);每条正则按 D10 有一红一绿(含"正确散文不误伤"的绿);D144 保留的 counter-evidence 句子不删。

### 1.7 `auditor/run.py`、`receipt/{build,schema,verify}.py`、`generator.py`、`cli/{build,main}.py`、`console/overview.py`(codex 改动)

- `run.py`:阶梯整体替换为 `decide_authority(...)`,`AuditOutcome` 加 `authority: dict`,报告新增两行(`| evidence authority | **X** via `route` |`,`| evidence policy | ... |`)和 "## Authority routing" 段。我们线 run.py 自 base 只 +21 行(NOTHING_AUDITED + provider-wait 重抛),**结构相同,可定位**;但要把 `scope_started`、`PROVIDER_WAIT_CATEGORIES` 重抛保留。
- `receipt/build.py`:可选 `receipt["authority"]`;我们线 build.py +97(ToolEvidence 三态、`EVIDENCE_BROKEN` 拒签 D125)——**不冲突**,追加一个可选键即可。
- `receipt/schema.py`:`validate()` 里校验 authority 块并要求 `authority.workflow_verdict == audit.verdict`;我们线 +52(签名/复现相关)——不冲突。
- `receipt/verify.py`:报告行正则绑定 + `admission_shortfalls` + `admit()` 拒绝非 PASS/ADVISORY;我们线 +435(DSSE 签名、ledger 再推导、controller 记录校验)——**插入点仍在**(`verify.py:449-453` 报告 verdict 行、`:467` shortfalls、`:551` admit),可吸收。
- `generator.py`:system prompt 改写(删掉 "state in notes why the finding rests on a misreading, so a human can route it as a dispute",改成 "stop in notes so a human can judge the tradeoff")+ `render_findings(verified_only=)` + FINDINGS 段标题改 "VERIFIED FAILURES"。我们线 generator.py +368(file_identity 绑定、格式修复、skills/MCP/HPC 段)。**prompt 改写与 D144 冲突**(D144 明确保留 dispute 路由句并要求两种回应并列);`verified_only` 让 ADVISORY 永远不到生成端。
- `cli/main.py`:`_provider_stop_reason` 读 `authority.rationale`;`cmd_run` 打印 `AUTHORITY: X -> route`。CLI 是引擎接口(DESIGN §7),打印协议词可接受。
- `console/overview.py`:pipeline "Verdict" 行改为 `f"{verdict} · authority {status} -> {route}"`,escalation 卡片按 `route == "git-governance"` 换文案。**这是产品面**(PRODUCT_VISION §1 "Users must never need the internal vocabulary";North Star §12 "no raw internal event names in primary UI")——`git-governance`、`automatic-repair` 这类路由名不能上主面。我们线 overview.py +177(D141 "a defect was caught" 改动在 finding-states 分支),插入点仍在(`overview.py:394-402`)。

---

## 2. 我们侧是否已有"authority"概念(按名/按义)

| 我们侧概念 | 位置 | 与 codex `authority` 的关系 |
|---|---|---|
| `policy/` — `CapabilityToken` + `policy.decide(proposal, token)` | `policy/__init__.py:1-9`, `policy/engine.py:1-11` | **同名不同义**:这是"一个动作可否执行"(能力授权,level 0–6),不是"一个 finding 有多大阻断权"。同为 fail-closed、不询问模型。`policy.decide` vs `authority.decide` 会撞名。 |
| `broker/` + `ledger/` — 每个模型动作过 broker、写哈希链 | `broker/__init__.py:1-13`, `ledger/chain.py:1-20` | **证据来源**:工具证据(`ToolSpec.evidence_fields`,`tools_research.py:368-377` 的 `source_ids`/`content_sha256`)是第三种"机制族",已 digest 绑定;codex 没纳入。 |
| `dcl/` — verdict-in-code,`Finding(severity, rule, artifact, observation, check)`,`CheckContext.governed_source_ids` | `dcl/framework.py:65-70`, `:61` | codex 的 `checker:{check}` / `deterministic:{check}` 就是从这里派生的,可直接复用 `check` 字段。 |
| `admission.py` — 部署档位 local/remote/paired/enforced | `admission.py:1-33` | **词汇冲突**:codex 的 `route="admission"` 与此三义(还有 `verify.admit()`)。 |
| `dispute.py` + `cmd_resolve` + `controller/state.py` ESCALATED 锁 | `dispute.py:1-22`, `cli/main.py:1212`, `controller/state.py:65,215-226,294-310` | 这就是 codex 的 "git-governance" 路由的**实体**;已存在。D142 第三项(申诉不经原审计端)尚未做。 |
| D141–D147 决策 | `DECISIONS.md:6135-6495` | 与 codex 同一命题("模型 finding 是可争议证据;确定性层是硬地板"),但我们选择先做 finding 状态、量确认率,再定默认。 |
| `feat/finding-states` | 分支 f85d92a | `tier`+`state` ≈ codex `mechanism_family`(粗粒度)+`verified`;见 Q4。 |

结论:authority **不是**已有概念的重名,也不与 `policy/` 冲突(不同问题),它填的是"裁决依据的可验证记录"这个空;但它的**路由改变**部分与我们的决策序列冲突。

---

## 3. Q1–Q6

### Q1 — 单一模型 BLOCKER → ESCALATE、永不自动 BLOCK,与"允许只咨询的宪法"(D143)一致、重复还是矛盾?用户面变化?

**部分重叠、并在关键处矛盾。**

- D143 的裁定是:**由宪法作者选择**模型有没有阻断权(全 ADVISORY → 模型永不 gate;确定性地板仍在,D147 证明地板不依赖渲染器)。codex 的规则是:**无论宪法怎么写**,模型 BLOCKER 都不 gate、都升级给人。两者都保住了地板;但 codex 把宪法里 `severity: BLOCKER` 对模型规则的含义改成了"升级给人",`ADVISORY` 变"记录"。作者选了 BLOCKER 也拿不到"自动修订一轮"——这是**把 D143 交给作者的旋钮又收回**。
- D142 明文:"`Observe` as the default … does not become the default because a good reviewer reasoned well … Finding states come first — then the number decides."(`DECISIONS.md:6241-6247`)。codex 的规则**就是** Observe-默认(模型 BLOCKER 不阻断)以策略常量形式落地,没有确认率数据。与 D142 的顺序矛盾。
- D144 裁定保留 counter-evidence 句并把"修"与"举证"并列(`DECISIONS.md:6345-6349`);codex 的 `generator.py` 改写删掉了 dispute 路由句。矛盾。
- 产品面**有变化**:
  - 今天:模型 BLOCKER → `BLOCKED` → 生成端自动修订(最多 `max_rounds`)→ 穷尽后 ESCALATE(`tests/test_loop_integrity.py:255` `test_three_cli_build_revisions_remain_one_cycle_and_end_escalated`)。用户看到 "正在修订"。
  - codex:第一轮就 `ESCALATE` → "需要你决定"(codex 把上述测试改成 `test_model_blocker_stops_before_defensive_revision_loop`,单轮即 `EXIT_ESCALATED`)。这是 North Star §14 "revision rounds run automatically … On exhaustion, a decision interface" 与 §37 "revision rounds run automatically" 的**反转**,V5 不变量 5 "Automatic revision is bounded; unresolved work becomes an explicit human task" 的前半句消失。
  - 另外 codex 让 `NON_EVIDENTIAL` 回放 PASS 也变 ESCALATE;我们的 fixture 流程(以及 `tests/test_loop_integrity.py:187`)依赖回放 PASS 走通,需评估 332 提交里新增的回放测试受影响面(本报告未跑测试,标为未知)。
- 一个**独立于产品裁定的 bug**:`dd725d3:authority.py decide()` 把 `hard or consensus → BLOCK` 放在 `elif escalation_lock` 之前。今天 `run.py:237-238` 锁最先。后果:一个已 ESCALATED 的 cycle,若下一次提交带 DCL 硬失败,codex 会给 `BLOCKED/automatic-repair` 并回到生成端修订——绕过了人类管辖(`controller/state.py:215-226` 记录 `blocked_by_escalation` 的初衷)。原样嫁接会引入回归。

**结论**:"模型置信度和厂商身份本身不授予阻断权"这条**性质**与我们一致;"因此第一轮就升级给人"这条**路由**与 D142/D143/D144 和产品文档冲突,且不该是默认。合理形态是**档位**(与 `checks:` 的 off/general/science/research 同构):`model_blocker: revise`(默认,今天的行为,finding 标 `alleged`)| `escalate`(codex 行为)。

### Q2 — "≥2 producers ∧ ≥2 mechanism families" 的 consensus 路径今天是死代码,可以留吗?

**生产中可证明不可达,不只是"暂未用到"。** `records_from_audit` 只产两类记录:DCL(verified=True,BLOCKER 时 `evidence_type=deterministic_failure` ∈ `HARD_EVIDENCE`)与模型(verified=False)。consensus 只对"verified ∧ BLOCKER ∧ 非 hard"的记录有意义——这类记录**没有任何生产路径能生成**(测试里靠 `evidence_type="documentary"` 手工构造)。所以 `hard` 是 `consensus` 的严格超集,consensus 分支永远不是决定分支。

按我们的决策:

- D141(`sealed` 名字宣称代码没有的能力)、D146(守卫名超出其覆盖)、D64(假检查)——README/DESIGN 里写 "corroboration across distinct producers and mechanism families" 就是在宣称一个不可达能力。
- D10 "a guard must be shown to fail":`test_cloned_mechanism_cannot_manufacture_consensus` 与 `test_distinct_producers_and_mechanisms_can_corroborate` 只能用 fixture 触发,是 D59 意义上的自证式测试。
- V5 复杂度预算与 North Star §35 "Simplify before adding"。

**建议:剥掉 consensus 分支和 `HARD_EVIDENCE` 之外的 `evidence_type` 枚举**,只留 `verified`/`state` 语义;在 `POLICY_VERSION` 上预留升级(`-v2` 引入多 producer 时再加),文档写成"扩展点,当前无第二个 producer"。若坚持保留,至少 README/DESIGN 不得把它写成现行准入规则,且需要一个生产路径级的 producer(例如把 broker 工具证据或第二审计端注册为 producer)让它真正可达。

### Q3 — `authority.py` 在 v5 布局下放哪?

- 它做的是**verdict 合成的依据记录**——`auditor/run.py:1-3` 自述 "Verdict synthesis is code, never model output (I4)",所以归 `auditor/`。建议 `src/crossaudit/auditor/authority.py`,导出 `records_from_audit`, `decide_authority`, `validate_block`(避免与 `policy.decide` 撞名)。
- **不进 `policy/`**:`policy/` 是能力授权引擎(token/level),混入 finding 权限会让"policy"一词双义;`policy/engine.py:1-11` 的职责声明也不容纳它。
- **不做顶层新包**:顶层已经有 `admission.py`(部署档位)、`dispute.py`、`autonomy.py`;再加 `authority.py` 会让"admission/authority/autonomy/policy"四个近义词并列。
- 内核规则("`auditor/ broker/ ledger/ policy/ dcl/` 只能加不能削,向后兼容"):
  - 新增模块 = 加,合规。
  - `run.py` 阶梯替换 = 改;**只有在 verdict 集合与既有输入→verdict 映射不变时**才算向后兼容。codex 版本改变了两个映射(模型 BLOCKER→ESCALATE;NON_EVIDENTIAL PASS→ESCALATE)并回退了锁优先级——不合规,须走决策记录。
  - `receipt` 加可选 `authority` 键、`verify` 加条件校验 = 加,合规(旧回执无该键照旧验)。
- `repair_guard.py`:不属于内核五包;放顶层或 `cli/`。

### Q4 — 证据词汇是否该复用我们已有的来源?

**应复用,且大部分已有:**

| codex 字段 | 我们已有的来源 | 建议 |
|---|---|---|
| `producer_id="checker:{check}"` | `dcl/framework.py:70 Finding.check`;`app.py:159 dcl_source_digest()` 把检查层源码摘要绑进回执 | 用 `check` 名 + 已绑定的 `dcl_source_sha256`,不再拼字符串 |
| `producer_id="auditor:{vendor}/{provider}:{model}"` | `run.py:198-206 exchange{provider,vendor,model,base_url,fallback,reasoning_effort}`;回执 `audit.{provider,model,vendor,fallback}` | 引用回执 `audit` 块,不重复;必要时加 `exchange` 的 `reasoning_effort` |
| `mechanism_family` | finding-states `tier ∈ {deterministic, model}`;broker 工具证据是第三族(`ledger.KINDS`, `ToolSpec.evidence_fields`) | 用 `tier`,枚举 `deterministic | model | tool | human`(human = `resolve`/dispute 裁决) |
| `verified: bool` + `verification_reason` | finding-states `state ∈ {alleged, confirmed, fixed, withdrawn, overridden, unresolved}` | 用 `state`;`verified` ≡ `state == confirmed`;`verification_reason` 可留作 `state_reason` |
| `evidence_type ∈ {deterministic_failure, executable_counterexample, reproducible_observation, textual_judgment}` | 无;`executable_counterexample` 无生产者 | 删;由 `tier`+`severity` 推出 |
| `finding_key = "{rule}@{artifact}"` | `dispute.py:60-64 Finding(severity, rule, artifact, observation)` 与 `FINDING_LINE` 正则 | 同构,可采 |
| 工具证据(`web_fetch`/`paper_search` 的 `source_ids`、`content_sha256`;`file_write` 的 `pre/post_sha256`) | `tools_research.py:263-297`, `tools_write.py:182-189`;`dcl/provenance.py` 已消费 `governed_source_ids` | codex 完全没纳入;这是我们线上**唯一已 digest 绑定的第三 producer**,若要 consensus 有意义,它是第一个候选 |

**finding-states vs codex 的 `verified`/severity:同一条轴,不矛盾。** `severity` 是"多严重"(BLOCKER/ADVISORY,宪法作者定),`state`/`verified` 是"是否成立"(系统知道多少)。codex 把 severity 和 verified 一起用来算权限,finding-states 只记状态不裁决——**两者都承认 BLOCKER 曾一词两义**(finding-states 的 `framework.py` 注释与 codex 的 docstring 说的是同一句话)。差别只在落点(sidecar vs 回执)与是否裁决。

### Q5 — 文档哪些仍真、哪些要重写;README/DESIGN 能否吸收?

见 §1.3–1.5。摘要:

- **仍真**:两平面分层;工作流映射表;"metadata, not proof";TCB 列表;旧回执可验;回执绑定块的字段设计。
- **要重写**:Evidence Lab 来源;consensus 作为现行规则;"only verified machine blockers returned";`crossaudit.authority` 路径;`admission` 路由名;补 `NOTHING_AUDITED`;把"lone model BLOCKER → governance"从事实改为档位说明。
- **README**:hunks 不重叠,文本可合;三处语义承诺(流程图、状态表释义、"Only verified machine blockers" 段)只在行为采纳后写入;`repair:` 配置块随 RepairGuard 切片走。
- **DESIGN.md**:我们未改,补丁干净;但它是协议权威,内容须与 D148+ 决策一致后再改。分层图把 DCL 从"引擎"挪到"证据准入"层与 D143 "确定性地板"叙事相合,可采。

### Q6 — 命名/词汇碰撞:codex `PASS/ADVISORY/BLOCK/ESCALATE` + `PASS/BLOCKED/ESCALATE/DCL_ONLY` 与我们 HEAD 是否一致?

- 工作流 verdict:`receipt/schema.py:33 VERDICTS = ("PASS", "BLOCKED", "ESCALATE", "DCL_ONLY")`;`run.py:237-261` 产出同一集合;`errors.py:23-24` `EXIT_BLOCKED`/`EXIT_ESCALATED`;controller 状态 `OPEN/BLOCKED/PASSED/ESCALATED/CONSUMED`(`controller/state.py:65`)。**codex 的 `workflow_verdict` 集合与 HEAD 完全一致。**
- authority status:`BLOCK`(非 `BLOCKED`)是新拼法,与 verdict `BLOCKED`、controller `BLOCKED`、severity `BLOCKER` 并存——四个近形词。`ADVISORY` 作为 status 与 severity `ADVISORY`(`validate.py:13`, `constitution.py:25`, `framework.py:16`)**同词异义**:一个 finding 可以是 severity=ADVISORY,一个 cycle 可以是 status=ADVISORY,而 finding-states 又加了第三轴 `state`。建议 status 改用不与 severity 重名的词,或干脆不引入独立 status,只在回执里记 `blocking_evidence_ids`/`advisory_evidence_ids` 的**派生结果**(空/非空)——status 是它们的函数,不必成为第四个词汇表。
- `route` 值(`admission`, `automatic-repair`, `git-governance`, `obtain-audit`):`admission` 三义(见 Q3);其余是内部词,**不能上 console 主面**(PRODUCT_VISION §1 六态;North Star §12),CLI 可以。
- finding-states 的守卫 `test_no_user_facing_surface_renders_a_state_word` 扫描 `console/page.py` 的引号字符串;codex 加进 page.py 的 ZH 文案不含状态词,不会触红;但其 overview 的 `authority {status} -> {route}` 会。

---

## 4. 总体融合策略建议

**推荐:re-express(用我们的词汇重述其性质)+ 局部原样嫁接。** 不是 "graft as-is",也不是 "graft with modifications"——因为要改的不只是代码位置,而是**默认行为与词汇轴**,那已经是重述。

### 4.1 理由

1. codex 的三条实质性质里,一条我们已覆盖并有守卫(地板,D147),一条我们已有更一般的形式在分支上(`verified` ⊂ finding-states),只有一条是新的(裁决依据绑定进回执)——而那一条不依赖 codex 的路由改变。
2. codex 的路由改变(模型 BLOCKER 不修订直接升级)与 D142 的决策顺序、North Star §14/§37、V5 不变量 5 冲突;按我们自己的规则,它必须先有确认率数据再成为默认。作为**档位**它是合理的(与"strictness is a dial, not the identity"的定位一致)。
3. `decide()` 的锁优先级回退、`scope_started` 缺失、NON_EVIDENTIAL 语义改变——原样嫁接会在内核引入三处行为变化,违反"只加不削、向后兼容"。
4. consensus 路径生产不可达,留着即 D141/D146 类问题。
5. RepairGuard 是真正的空白,但正则误伤散文,按 D121 不能以现状合;独立切片。

### 4.2 具体配方(按切片,每片独立复核)

**切片 A — `feat/finding-states` 先合**(已完成未复核;它是 B 的前置)。

**切片 B — `auditor/authority.py`(重述版)**
- `EvidenceRecord`:`evidence_id, finding_key, severity, tier, state, claim, artifact, producer, producer_digest`(`producer` = `check` 名或回执 `audit` 块引用;`producer_digest` = `dcl_source_sha256` 或 provider 路由摘要)。
- `records_from_audit` 复用 `finding_states()`(finding-states 分支)而非重新拼字符串。
- `decide_authority(records, *, escalation_lock, scope_started, invalid, bounded, no_model, non_evidential, auditor_escalate)`:**v1 只派生**——`blocking_evidence_ids`(`state == confirmed ∧ severity == BLOCKER`)、`advisory_evidence_ids`、`rationale`、`evidence_digest`;`workflow_verdict` **直接取 `run.py` 现有阶梯的结果**并断言一致性(hard 集合非空 ⇒ verdict==BLOCKED)。锁最先。不引入 `BLOCK`/`ADVISORY` status;`requires_human` 从 verdict 派生。
- `validate_block` 原样吸收(改字段名),摘要突变测试原样吸收。
- 回执:可选 `authority` 键(codex 形状);`schema.validate` 与 `verify` 的报告行/`admit` 校验原样吸收。**同时**决定 finding-states 的 sidecar 是否保留:建议保留 `findings.json`(人读/UI 用)且回执块只含 `evidence_id`+`state`+`producer_digest`(不含 `claim` 全文,避免报告散文进摘要两次)。
- 不改 `generator.py` prompt(D144 已定);不加 `render_findings(verified_only)`。
- console 主面不显示 route;Inspector(North Star §12 "evidence references")可显示。

**切片 C — 档位 `audit.model_blocker: revise | escalate`**(等 finding-states 跑出确认率后再议默认;D142)。`escalate` 档 = codex 行为:`state == alleged ∧ BLOCKER` → `ESCALATE/git-governance`,第一轮即 `WAITING_FOR_HUMAN`。这时才把 README 流程图/状态表与 DESIGN §7.1 写成"档位说明"。

**切片 D — `repair_guard.py`**(独立):分域正则、D10 红绿、在我们 `build.py` 的 BLOCKED→revision 路径(`build.py:973-977`)重新定位插入点;`RepairPolicy` 配置与 scaffold 模板随之;只对 `DCL:` 规则触发的修复轮生效这一点在文档里如实写。

**切片 E — 文档**:`docs/EVIDENCE_GOVERNANCE_FUSION.md` 重写为 `docs/EVIDENCE_AUTHORITY.md`(来源 D141–D147 + finding-states;consensus 标为扩展点);DESIGN §7 四层图与 "auditor (proposes)" 采纳;README 三处语义承诺随切片 C。

### 4.3 需要 owner 裁定的问题(不由工程师定)

1. 模型 BLOCKER 的默认路由(revise vs escalate)——D142 已说要数据;是否接受"先做档位、默认 revise"。
2. 裁决依据记录进回执(digest 绑定)还是留 sidecar——finding-states 分支的作者选了 sidecar 并写了守卫;codex 选了回执。两者都保旧回执可验;取回执意味着修改 finding-states 的 `test_the_state_never_reaches_a_receipt_or_its_digest`。
3. consensus 路径:删,或先注册第二个 producer(broker 工具证据)让它可达。

---

## 附:关键引用索引

- codex:`dd725d3:src/crossaudit/authority.py`(`decide` 阶梯顺序;`records_from_audit`);`dd725d3:src/crossaudit/auditor/run.py` diff(阶梯替换、报告两行);`dd725d3:tests/test_loop_integrity.py` diff(`PASS→ESCALATE`;三轮测试改单轮);`dd725d3:src/crossaudit/generator.py` diff(prompt 改写);`dd725d3:src/crossaudit/console/overview.py` diff(主面显示 route)。
- 我们:`src/crossaudit/auditor/run.py:1-11, 237-265`;`receipt/schema.py:33`;`auditor/validate.py:13, 70-74`;`constitution.py:130-149`;`dcl/framework.py:16, 61, 65-70`;`policy/__init__.py:1-9`;`broker/__init__.py:1-13`;`ledger/chain.py:36-39, 99-107`;`admission.py:1-33`;`dispute.py:1-22`;`controller/state.py:65, 215-226`;`receipt/build.py:106-171`;`receipt/verify.py:449-453, 467, 543-558`;`console/overview.py:394-402`;`cli/build.py:965-977`。
- 决策:D10, D59, D64, D121, D125, D131, D132, D133, D141, D142, D143, D144, D146, D147(`docs/DECISIONS.md:378, 2342, 2597, 5121, 5326, 5630, 5710, 5768, 6135, 6189, 6249, 6305, 6406, 6456`)。
- 文档:`docs/V5_KERNEL_ARCHITECTURE.md`(不变量 3、4、5;Safe autonomy policy);`docs/NORTH_STAR.md` §12, §14, §31, §37;`docs/PRODUCT_VISION.md` §1, §2;`docs/RESTART.md` "下一步" 与 "不可动摇的规矩";`docs/findings/auditor3-advisory-only-4db0c7e.md`;`feat/finding-states:docs/findings/w1-finding-states.md`。
