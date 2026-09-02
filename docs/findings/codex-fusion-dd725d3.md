# codex `evidence-governance-fusion` (dd725d3) × v5-redesign (c170c17) — 逐文件对比与融合方案

写于 2026-09-02。merge-base `7ded699`。只读分析，未合并、未推送、未改内核代码。
三份分簇原始报告归档于同目录 `codex-fusion-dd725d3-A-kernel.md`、`-B-design.md`、`-C-cli-console.md`。

## 0. 一句话结论

两条线回答同一个问题（"审计激励制造防御性编程、模型单方判定不能自动变成修复指令"），
**方向一致、机制互补**：codex 加了一层**证据授权**（`authority.py` + 回执 `authority` 块 + `repair_guard.py`），
我们这条线做的是**去激励**（D141–D147：只咨询的宪法、finding 状态、prompt 侧重、空 scope 三态）。

但 codex 不能原样合。它对 `auditor/run.py` 判定阶梯的**整体替换**在四处违反内核规矩，其中两处是真正的削弱：

| # | 问题 | 性质 |
|---|---|---|
| 1 | `decide()` 把 `hard or consensus → BLOCK` 排在 `escalation_lock` **之前**：已升级给人的 cycle 若下一次提交带 DCL 硬失败，会回到 BLOCKED/自动修复，绕过人类管辖 | **削弱**（回退 `run.py:6`、`controller/state.py:215-226`） |
| 2 | `decide()` 没有 `scope_started` 输入：空 scope + 模型 PASS → PASS。w1 记录里"比报警更糟的唯一结果"回来了 | **削弱**（丢掉 7630592 的 NOTHING_AUDITED） |
| 3 | 模型单方 BLOCKER → 第一轮就 ESCALATE，不再走有界自动修订 | 产品级默认改变，D142 明确要求先量确认率再定；North Star §14/§37、V5 不变量 5 前半句消失 |
| 4 | `AuditOutcome.authority` 必填、`validate_block` 对 `policy_version` 硬相等、删除三轮回归测试 | 破坏向后兼容：手工构造 outcome 的测试 TypeError；策略升到 v2 后所有 v1 回执 IntegrityDenial |

**可近乎原样吸收的部分**（都是加法）：回执可选 `authority` 块 + `validate_block` 摘要绑定 + `verify.py` 报告行绑定与 `admit()` 拒绝 + 摘要突变测试；`generator.py` 三处 hunk；`config.py`/scaffold 的 `repair` 段；`repair_guard.py` 作为独立切片（正则须分域）。

## 1. 逐文件（18 个）

| 文件 | codex 做了什么 | 主线做了什么 | 关系 | 处置 |
|---|---|---|---|---|
| `authority.py`（新） | 证据记录 + 判定策略 + 回执块校验 | 无对应物；`policy/` 是能力授权（同名异义），finding-states 分支有 `tier`+`state` 同轴 | 互补，填空 | 重述后进 `auditor/authority.py`；见 §2 |
| `auditor/run.py` | 整个 if/elif 阶梯换成 `decide_authority()` | 插入 `scope_started` 守卫 + source_provenance ctx + tool_evidence | **冲突**（同一 hunk） | 保留主线阶梯原文，policy 作第二级只覆盖模型判定分支 |
| `receipt/build.py` | 可选 `receipt["authority"]` | tool_evidence 三态、sources、constitution_commit | 互补 | 追加，用 `if authority:` |
| `receipt/schema.py` | `validate()` 末尾校验 authority 块 + verdict 一致 | 三个可选块校验；`RECEIPT_SCHEMA` 双方都没 bump（=2） | 互补 | 追加第四个可选块；`policy_version` 改已知集合 |
| `receipt/verify.py`（已看） | 报告行正则绑定、shortfall、`admit()` 拒非 PASS/ADVISORY | +435 行（DSSE、ledger 再推导） | 互补，三个 hunk 干净 apply | 直接吸收 |
| `repair_guard.py`（新，已看） | 审 staged diff：越界/行数/防御性正则/二进制 | 无对应物 | 互补，填空 | 独立切片；`retry|fallback|skip` 正则对 Markdown 正文误报，只对代码后缀生效 |
| `generator.py`（已看） | `render_findings(verified_only=)`、prompt 改写、段标题 | +368 行，但被改的三处与 merge-base 逐字相同 | 可直接吸收 | 吸收，但**保留** D144 的 dispute 路由句；`verified_only` 只在档位开启时用 |
| `config.py` | `repair: {enabled, max_changed_lines}` | streaming、i18n、checks profile | 互补，三方合并零冲突 | 合入；加 `authority.lone_model_blocker: block|escalate`（默认 block） |
| `scaffold/__init__.py` | 模板加 `repair:` 段 | 未改 | 可直接吸收 | 在 config 认识新键**之后**合，否则 init→load 红 |
| `cli/build.py` | 只回传 `DCL:` BLOCKER、算 `repair_scope`、commit 前跑 guard、`git restore --staged` | +774 行；`with written:` 事务作用域、结构化升级 kind/cause | 互补 + 一处语义冲突 | guard 插在 `_staged_secret` 后；**不要**手写 restore，用 `AppliedFiles.rollback()`；加 `repair_refusal_used` 自愈一次；新 cause `repair_refused`/`evidence_governance` |
| `cli/main.py` | `_provider_stop_reason` 分支、receipt/JSON 透传、`AUTHORITY:` 行 | +876 行，已有 `_provider_stop_kind` 结构化 | 可直接吸收 | 合前两项；不加独立 `AUTHORITY:` 行 |
| `console/overview.py` | 解析报告行、Verdict 步 detail 并置两套词汇、升级卡 `requested` 换文案 | +177 行 | 互补，展示方式抵触 VDS §2 | 只吸收 `requested` 文案；`Cycle.authority*` 从 receipt 读；不改 pipeline detail、不加 attempts 列 |
| `console/page.py` | +1 行 ZH 译文 | +2276 行 | 可吸收 | 在 `openResolution` 加 `cause==='evidence_governance'` 分支，复用现有槽位；ZH 条目同步 |
| `tests/test_evidence_authority.py`（新） | 钉 8 条性质 | 无 | 可吸收 | (1)(5)(6)(7)(8) 原样；(2)(8) 参数化到档位；(3)(4) 随 consensus 处置 |
| `tests/test_loop_integrity.py` | replay PASS→ESCALATE；**删除**三轮回归测试 | 后半部分改 3 处，不重叠 | 语义冲突 | 保留主线断言与三轮测试；codex 新测试改成开启 `escalate` 档位 |
| `docs/EVIDENCE_GOVERNANCE_FUSION.md`（新） | 设计文档 | 无 | 部分成立 | 重写为 `docs/EVIDENCE_AUTHORITY.md`：去掉 "Evidence Lab"、consensus 降为扩展点、补 NOTHING_AUDITED、路径改 |
| `DESIGN.md` | 四层图、`auditor (proposes)`、§7.1 | 未改，补丁干净 | 可吸收 | DESIGN 是协议权威，先有决策再改；§7.1 写成档位说明 |
| `README.md` | 流程图、状态表释义、"only verified blockers" 段、`repair:` 块 | 4.15.0、签名回执、复现包、checks 档位 | 文本不重叠 | 三处语义承诺随档位切片走；`repair:` 随 guard 切片走 |

## 2. 融合方案（按切片，每片独立复核，顺序即依赖）

**切片 A — 先合 `feat/finding-states`。** 它是 B 的前置：codex 的 `verified: bool` 就是 `state == confirmed`，`mechanism_family` 就是 `tier`。

**切片 B — `auditor/authority.py`（重述版）+ 回执块。**
- `EvidenceRecord` 字段用我们的词：`evidence_id, finding_key, severity, tier, state, claim, artifact, producer, producer_digest`。`producer` 是 `check` 名或回执 `audit` 块引用；`producer_digest` 是 `dcl_source_sha256` 或 provider 路由摘要。
- `records_from_audit` 复用 `finding_states()`，不再拼字符串。
- `decide_authority()` **v1 只派生**：`blocking_evidence_ids`、`advisory_evidence_ids`、`rationale`、`evidence_digest`；`workflow_verdict` 直接取 `run.py` 现有阶梯的结果并断言一致。锁最先；新增 `scope_started` 输入。不引入 `BLOCK`/`ADVISORY` 这一套第四词汇表。
- `run.py`：保留以 `if escalation_lock:` 开头、含 `scope_started` 的阶梯段落原文（`tests/test_empty_is_not_failed.py` 用源码文本守着）；`AuditOutcome.authority` 给 `field(default_factory=dict)`；`render_report` 加两行 + 一节。
- 回执：`build.py` 用 `if authority:`；`schema.py` 第四个可选块，`policy_version` 用 `KNOWN_POLICY_VERSIONS`；`verify.py` 三个 hunk 直接 apply；补 `blocking_evidence_ids ⊆ evidence ids` 校验。
- 需 owner 定：裁决依据进回执（digest 绑定，codex 选择）还是留 sidecar（finding-states 作者选择并写了守卫 `test_the_state_never_reaches_a_receipt_or_its_digest`）。

**切片 C — 档位 `authority.lone_model_blocker: block | escalate`。**
`block`（默认）= 今天行为：模型 BLOCKER 进有界修订，finding 标 `alleged`，回执诚实记录"未验证"。
`escalate` = codex 行为：第一轮即 `ESCALATE/git-governance`。
默认何时切换由 finding-states 跑出的确认率决定（D142）。README 流程图、状态表、DESIGN §7.1 在这一片写成档位说明。

**切片 D — `repair_guard.py` + `cli/build.py` 接线。**
放顶层，不进内核五包。越界/行数/二进制对所有文件生效；`DEFENSIVE_PATTERNS` 只对代码后缀的新增行生效（D121：守卫在正确内容上变红同样是缺陷）。每条正则按 D10 一红一绿，含"正确散文不误伤"的绿。插入点 `build.py` 的 `_staged_secret` 之后、commit 之前；拒绝走 `with written:` 的事务回滚，把被拒 diff 摘要写进 findings 文本；`repair_refusal_used` 只免费重问一次。

**切片 E — 文档。** `EVIDENCE_GOVERNANCE_FUSION.md` → `EVIDENCE_AUTHORITY.md`；DESIGN 四层图和 `auditor (proposes)` 采纳；README 三处承诺随 C。

## 3. consensus 路径的处置

"≥2 producers ∧ ≥2 mechanism families" 在生产中**可证明不可达**：`records_from_audit` 只产两类记录，DCL BLOCKER 已在 `HARD_EVIDENCE` 里，模型记录 `verified=False`，所以 `hard ⊇ consensus`，consensus 分支永远不是决定分支。codex 自己的测试要靠 fixture 里的 `evidence_type="documentary"` 才能触发。
按 D141/D146（名字宣称代码没有的能力）应剥掉，`POLICY_VERSION` 预留 v2。若要它真实可达，第一个候选 producer 是 broker 工具证据（`source_ids`/`content_sha256` 已 digest 绑定），codex 完全没纳入。

## 4. 测试事实

- 测试运行陷阱：`crossaudit_v4/.venv` 的 site-packages 装了旧 `crossaudit`，不带 `PYTHONPATH=…/crossaudit_integ/src` 跑的是旧包（7 个假失败 / `crossaudit.broker` collect error）。
- HEAD 基线（带 PYTHONPATH）：内核簇 14 个文件 193 passed；CLI/console `-k "build or console or main or cli"` 194 passed。
- codex 原样合会红的主线测试：`test_empty_is_not_failed`（源码文本）、`test_committed_audit_bytes.py:41`（TypeError）、`test_loop_integrity.py:187`（replay PASS）、`test_loop_integrity.py:255`（三轮）、`test_advisory_only_constitution…still_passes_clean_work`。
- 建议新增两条守卫：空 scope + 模型 PASS 真跑 `run_audit` → verdict ≠ PASS（现有测试只查源码文本）；`escalation_lock=True` + DCL 硬失败 → ESCALATE（目前无测试直接断言，codex 会给 BLOCKED）。

## 5. 需要 owner 裁定的三件事

1. 模型 BLOCKER 的默认路由：接受"先做档位、默认 `block`"，还是直接采 codex 的 `escalate`。
2. 裁决依据落点：回执（digest 绑定）还是 sidecar。
3. consensus 路径：删，或先注册第二个 producer 让它可达。
