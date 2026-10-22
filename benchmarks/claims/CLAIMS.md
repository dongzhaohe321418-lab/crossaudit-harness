# What CrossAudit says it does, and how each claim is checked

Written 2026-10-21 before the first run. Each row is one sentence the public
README (or SECURITY.md) makes, turned into a test a stranger could run with no
knowledge of the code: install the package the way the README says, drive the
CLI the way the README says, and look at what comes back. A claim the harness
cannot exercise here is marked for what it needs; it is never marked PASS.

The loop this serves: run the harness on `main` (what `pipx install …@main`
gives a user), record every FAIL, fix on a branch, run again, repeat until the
README and the product agree. Results go to `RESULTS-<ref>.md`, one per git
ref, rendered from `records/<ref>/claims.jsonl`.

## How the model side is exercised without money

The provider adapters accept a loopback `base_url` for an explicitly trusted
custom origin (README "Provider and model support": "an explicitly trusted
custom OpenAI-compatible endpoint for CLI deployments"; `providers/anthropic.py`
and `providers/openai_compat.py` both pass `allow_insecure_localhost=True`).
The harness therefore runs two **fake provider servers** on 127.0.0.1, one
speaking the OpenAI chat-completions contract and one the Anthropic messages
contract, each driven by a scripted scenario, and points the two roles of a
real project at them. Everything else — `init`, the git ledger, the
deterministic checks, the auditor prompt, reply validation, repair, receipts,
signing, verification, admission, exit codes, the console — is the shipped
product. The pair is a genuine cross-vendor pair as the product sees it
(`anthropic` ↔ `openai`); what is faked is only the model's text. Where a
claim is about model *quality* (does the auditor catch real defects), the
fake cannot speak to it and the row says so.

Vocabulary: **PASS** the observed behaviour matches the sentence; **FAIL** it
does not (evidence attached); **PARTIAL** the mechanism works but the sentence
overstates it (evidence attached, the gap named); **UNTESTED(needs: …)** not
exercised here, with what it would take.

## Claims

### A. Install and first contact

| id | README says | test | pass when |
|---|---|---|---|
| C01 | `pipx install "git+https://github.com/dongzhaohe321418-lab/crossaudit-harness@main"` then `crossaudit --version` works ("Command line (Python 3.10 or newer)") | On a machine without pipx (this one), follow the sentence literally; then the documented alternative `pip install "crossaudit @ git+…@<ref>"` into a fresh venv | the literal command's prerequisite is stated (pipx) or the fallback is given in the same place; the fallback installs and `--version` prints the version and install mode |
| C02 | "Installing asks for nothing and contacts no provider; setup begins with `crossaudit init`" | install in a venv with all provider key variables unset and `HTTP(S)_PROXY` pointed at a dead port; observe no outbound connection except the git clone | no request leaves except the package fetch |
| C03 | "`crossaudit init my-project --no-console --auditor-vendor … --generator-vendor …` creates the project, initialises git, stores credentials outside the repository in a mode-600 file, turns requirements into versioned rules, commits the initial configuration" | run it non-interactively with the two fake vendors (`openai`, `anthropic`) and key variables set to dummy values; inspect the tree, `git log`, the keys file mode, `AUDIT_RULES.md`, `DETERMINISTIC_CHECKS.md` | a git repo with ≥ 1 commit, `crossaudit.yml`, `AUDIT_RULES.md` with rule ids, `DETERMINISTIC_CHECKS.md` naming exactly the checks the README's first "Deterministic checks" table lists (read at the ref under test), a keys file outside the repo with mode 600 or an init message naming `CROSSAUDIT_AUDITOR_KEY`/`CROSSAUDIT_GENERATOR_KEY`, no key in any committed file |
| C04 | "`crossaudit doctor` checks Python, Git, package identity, TLS certificates, configuration, credentials, vendor separation, the rule file, state storage, and the current admission tier. It is read-only unless `--fix`" | run `doctor` and `--json doctor`; hash the project tree before and after | every listed item appears as a posture line; tree hash unchanged; exit 0 on a healthy project |
| C05 | "Same-vendor pairs are refused" / "The generator and auditor must use different vendors" | `init` with `--auditor-vendor openai --generator-vendor openai`; also edit a good `crossaudit.yml` to the same vendor and run `doctor` and `build` | `init` refuses (exit 20) or `doctor` reports heterogeneity failed and `build` refuses before any provider call (exit 20); the fake servers log zero requests |

### B. The loop

| id | README says | test | pass when |
|---|---|---|---|
| C06 | "`crossaudit build "task"` commits the task, asks the generator to create or revise files, commits that round, runs deterministic checks, asks the independent auditor to review the committed tree, and records the verdict" — producing the commit sequence task → generator round → audit report → receipt | scenario **clean**: generator returns a complete, rule-abiding increment; auditor returns PASS | exit 0; `git log` shows exactly that commit sequence; `cycles/<id>/{report.md, checks.json, findings.json, receipt.json}` exist; `status` shows PASS |
| C07 | "If the auditor reports a BLOCKER, the findings are returned to the generator for another round. The default maximum is three rounds." | scenario **fix-on-2**: auditor BLOCKED in round 1 with a finding; generator's second reply addresses it; auditor PASS in round 2 | exit 0; two generator rounds in `git log`; the round-2 generator prompt (captured by the fake) contains the round-1 finding text; final PASS |
| C08 | "An exhausted budget escalates; it never approves." / "If the result still has blockers at the limit, CrossAudit pauses and escalates to the user; it never converts a failure into PASS." | scenario **always-blocked** with `max_rounds: 2` | exit 11; `status` shows ESCALATED; no PASS receipt; exactly 2 generator rounds; the fake saw no third generation call |
| C09 | "Deterministic checks run over the committed files first … a failed check blocks whatever the model says" | scenario **dcl-fail**: generator writes `results.json` with a quantity lacking a unit; auditor replies PASS anyway | verdict BLOCKED; `checks.json` names CA-DATA-001; no PASS receipt; `build` exits with the loop's final state (11 once the round budget is spent — README "Exit codes" since D172), `audit` on that increment exits 10 |
| C10 | "`crossaudit audit --offline` returns `DCL_ONLY`, never PASS" and "`crossaudit check` runs deterministic checks only" | run both on the clean project | `check` exit 0 with `verdict: PASS` for the deterministic layer only; `audit --offline` reports DCL_ONLY and exit 11; no provider request |
| C11 | "A model-only blocker is recorded as unverified evidence; whether it drives a revision or a human decision is a project dial (`authority.lone_model_blocker`), and the receipt says which" | scenario **always-blocked** twice: dial `block` (default) and dial `escalate` | with `block`: a second generator round happens; with `escalate`: no second round, ESCALATED after round 1; the receipt's authority block names the dial value |
| C12 | "each revision is screened by a repair guard before it is committed … a file outside the audited scope is refused" | scenario **escape**: round-2 generator reply writes `../../evil.txt` and a file at repo root | the out-of-scope file is never committed; the round is refused or re-asked; exit ≠ 0 unless a later honest round passes |
| C13 | "the reply from the provider is cut off at a token limit … the partial reply was discarded" (CHANGELOG Unreleased, D167; README's loop description implies a committed file is complete) | scenario **truncated**: the fake generator returns a reply with `finish_reason: "length"` whose last file block has no END marker | **on main**: expected FAIL (the half file is committed — the known defect); **from the fix branch on**: no file committed, the run parks ESCALATED with a provider escalation naming the cut-off, and `build` exits 22 (provider failure) on trees that carry D172, 11 before it; this row is the loop's first measured improvement |
| C14 | "Every task, round, commit, check result, finding with its tier and state, verdict, and human decision, committed to Git; governed actions go to an append-only hash-chained ledger" | after the fix-on-2 scenario, list what git holds and what `.crossaudit/` holds | `findings.json` carries tier and state per finding; the report's Evidence table lists tier; `git log` is append-only (no amend/rewrite); if an evidence ledger file exists it verifies |

### C. Receipts, verification, admission

| id | README says | test | pass when |
|---|---|---|---|
| C15 | "`crossaudit verify <receipt>` re-derives every binding; a changed byte fails it" | verify the clean PASS receipt; then flip one byte in `report.md` (committed), in `AUDIT_RULES.md` at the audited commit (rewrite history is not possible, so instead edit `receipt.json`'s `report_sha256` and separately its `verdict`), and verify again | untampered: `BINDINGS VERIFIED`, exit 0; each tamper: exit 21 and the failing binding named |
| C16 | "Dry-run verification reports three distinct claims: BINDINGS VERIFIED, RECORDED, ADMISSION READY" | `verify` output on the clean receipt | all three lines present and true |
| C17 | "`verify --admit` consumes it once; reusing the same receipt is refused" | run `--admit` twice | first: exit 0 and admitted; second: refused with a non-zero exit (21 expected) and a sentence saying it was already consumed |
| C18 | "Each receipt is signed with the project's Ed25519 key … `receipt.dsse.json` sidecar … a present-but-invalid signature is refused … export the public key so anyone can verify offline without CrossAudit" | `export-pubkey > project.pem`; `verify --pubkey project.pem`; corrupt one byte of the signature → verify; delete the sidecar → verify; verify the DSSE signature **outside CrossAudit** with the `cryptography` library in the harness venv | pinned verify: SIGNED, exit 0; corrupted: refused, exit 21 (README's word is "refused"); deleted: the row records what happens (README does not say; the review found UNSIGNED/exit 0 — report as observed); external: the signature verifies over the DSSE PAE with the exported key |
| C19 | "`crossaudit reproduce <receipt>` shows the pinned dependency locks, whether your working tree still matches them, and the re-run steps" | commit a `requirements.txt` in the audited scope before the clean scenario; run `reproduce` | the lock's sha256 is in the receipt (the manifest or, for a lock already in the audited tree, the reproduction block's `tree_locks`, D171) and `reproduce` prints its path and hash, says the tree matches, and prints a re-run step; after editing the lock, says it drifted |
| C20 | "Exit codes are stable: 0, 10 BLOCKED, 11 ESCALATED/DCL_ONLY, 20 configuration, 21 integrity, 22 provider" | collect exit codes from C05, C06, C08, C09, C10, C15, C17 and a scenario where the fake provider returns HTTP 500 for every call | each matches the table, reading `build`'s code as the loop's final state: 0 PASS, 22 when every provider route failed, 11 for any other park (a check-blocked round that spends its budget included); `audit`/`run` report one cycle: 10 BLOCKED, 22 provider failure |
| C21 | "`--json` before the command name gives structured output" for `status`, `doctor`, `check`, `verify`, `routing` | run each with `--json` | valid JSON on stdout, nothing else on stdout |

### D. Safety and records

| id | README / SECURITY.md says | test | pass when |
|---|---|---|---|
| C22 | "The generator cannot edit the rule file, configuration, state, or audit ledger. It may write only inside the configured scope" | scenario **overreach**: generator reply writes `AUDIT_RULES.md`, `crossaudit.yml`, `cycles/x.md` | none of them changes in git; the round is refused/re-asked |
| C23 | "Usage data stays in `.crossaudit/usage.jsonl` … mode 600 … counts, time, role, phase, provider, and model only; prompts, generated text, request IDs, API keys … are never written" | after C07, read the file | exists with mode 600; every line parses; no line contains the dummy key, any prompt text, or any generated file content |
| C24 | "Credentials … go in a mode-600 file" and "secrets never enter a prompt/log/ledger/receipt" | grep the whole project tree, `.crossaudit/`, the console log and every fake-server-captured prompt for the dummy key values | zero hits outside the keys file |
| C25 | "`crossaudit resolve <cycle> --reopen/--close --because …` records a human decision … Resolution requires an interactive human terminal and cannot be produced by either model" | after C08, run `resolve` with stdin not a TTY; then under a pseudo-terminal (`script`/`pty`) | non-TTY: refused with a clear sentence; TTY: recorded, `status` shows the decision, the reason is in the ledger commit |
| C26 | "`crossaudit amend "…"` proposes and versions a rule change; rules never change in the middle of a cycle; an audit always cites the committed rule version" | run `amend` between cycles; then a clean scenario; inspect the receipt | a new rule commit; the next receipt's constitution hash equals the new commit's `AUDIT_RULES.md` blob |
| C27 | "`crossaudit init` writes `DETERMINISTIC_CHECKS.md` from the live check implementations. The same exact contract is included in the generator prompt, `doctor` output, Console, and `checks.json`" | compare the four texts | the contract strings are byte-identical across the file, the captured generator prompt, `doctor`, and `checks.json` |

### E. Console

| id | README says | test | pass when |
|---|---|---|---|
| C28 | "`crossaudit console` starts a local background server, opens the dashboard, and prints a tokenized localhost URL" | run once without a terminal (fetch the printed URL with urllib, bypassing proxies), then under a pseudo-terminal with `BROWSER` pointed at a logging script, then `--no-open` under the same terminal | HTTP 200 with the page; the URL carries a token; at a terminal the browser is invoked on that exact URL; `--no-open` and the non-terminal run invoke nothing |
| C29 | "Every HTTP request must carry an unguessable process token and an allowed localhost Host header" (SECURITY.md) | fetch without the token; with a wrong token; with `Host: evil.example` | 403/401 for each; the page only with the right token |
| C30 | "The console shows current activity, latest task and cycle state, recent PASS/BLOCKED/ESCALATED cycles, findings and reports, receipt and admission status" | after C06–C08, read `/api/state` (or the documented state endpoint) with the token | the JSON names the cycles and verdicts produced by the scenarios |
| C31 | "Closing the window / the server keeps running; `crossaudit console` manages it" | `console --stop` or the documented management verb | the server exits and the port closes |

### F. The offline halves of C33 and C34 (added in round 2)

Each row was split out of a round-1 "untestable" row: what can be exercised
with no account and no remote host is tested here; the remainder stays in G.
`gh` is a logging fake on `PATH` (shell script written by `run.py`); the MCP
server is `fakemcp.py`, a standard-library stdio JSON-RPC server with three
tools (`echo`, `big` returning 1,000,000 bytes, and `secret`, which is
advertised but never approved). C34b is the SSH/Slurm row in G, so the MCP
rows run C34a, C34c–C34g.

| id | README / SECURITY.md says | test | pass when |
|---|---|---|---|
| C33a | "Two-repository deployment": `crossaudit pair --science owner/work --audit owner/work-audit` — "Without `--apply`, `pair` prints the intended GitHub operations and changes nothing remotely" | in a project made by the documented `init`, run `pair` without `--apply` three times: `gh` absent from `PATH`, the fake `gh` answering `auth status` as signed out, and as signed in. Then, only to learn what the plan should have listed, `--apply` against the same fake with every `https://github.com/` URL rewritten to a local bare repository (`url.insteadOf` in the temp HOME, `GIT_ALLOW_PROTOCOL=file` so no other transport can be used). Also `init --github` with `gh` signed out, recorded as far as it goes (no device code is expected from the CLI: README says the device code is the app's **Connect GitHub**) | plan mode (no `--apply`) exits 0 whether `gh` is signed in, signed out or absent, prints every operation `--apply` performs with its commands, in order, names both repositories, lists what `--apply` does NOT do under its own heading, and changes nothing (the fake `gh` sees no creating or secret-setting call; tree, HEAD and remotes unchanged); signed out or absent, one line says what `--apply` will need; `--apply` with the fake `gh` signed in performs exactly the printed operations and nothing else (D173) |
| C34a | "Local stdio starts one exact executable and argument vector without a shell. The complete command is visible and requires explicit approval." "Connect a new server with Generator access disabled … then approve exact tool names and a calls-per-task cap." "During a task the Generator may emit one `tools/call` request at a time … results return to the same Generator turn … never become instructions to the Auditor" | the product has no MCP CLI verb (recorded from `--help`), so register the way the Tools & Skills dialog does: start `crossaudit console` (with a `fakemcp` copy A first on `PATH`), POST `/api/mcp` with the token — once without `approve_local_code`, then step 1 (connect, approval ticked, no tools, disabled) by the bare name `fakemcp`, a second *new* server enabled with `allow_all_tools`, step 2 (approve `echo`, `big`; cap 3; enable), then the same server with a different executable path (copy B) and no approval. Then `crossaudit build` with copy B first on `PATH`, the fake generator emitting four documented MCP-TOOL envelopes (`echo`, `big`, `secret`, `echo`) before its files | no process starts and the request is refused without the approval; the stored command is the resolved absolute path of copy A; the new enabled allow-all server is refused; changing the path without a new approval is refused and the stored path is unchanged; the build launches copy A only; `echo` reaches the server once and its text is in the next generator prompt; no tool output in any auditor prompt; build exit 0 |
| C34c | "approve exact tool names … New tools advertised later remain blocked until reviewed" / "per-tool allowlists" | in C34a's build, request 3 asks for `secret` (advertised, not approved) | the generator is told it was refused, the fake server never receives the call, the tool's marker text is in no prompt |
| C34d | "The controller validates the server, exact tool name, JSON argument size and saved call budget" / "call budgets" | C34a's build, cap 3: request 4 is a fourth `echo` | request 4 is refused with the calls-per-task sentence; the server received at most 3 calls and `echo` once |
| C34e | "Bounded text and structured results return to the same Generator turn" / "bounded results" | C34a's build, `big` returns 1,000,000 bytes of text | the generator prompt carries less than that, marked truncated (README states no number; the bound observed is recorded) |
| C34f | "The private local call ledger retains only server/tool identity, timing, status, and hashes of arguments/results—not their contents" / "content-free hashed call records" | after C34a's build read `.crossaudit/mcp/calls.json`; recompute `arguments_sha256` and `result_sha256` from the arguments sent and the bounded result the generator received; grep the whole project (git objects excluded) for the tool result text; if `.crossaudit/evidence.jsonl` exists, run its own `EvidenceLedger.verify()` | one row per executed call, keys only identity/timing/status/hashes, both hashes recompute, mode 600, no result text in the file or anywhere in the project; the row records whether the hash-chained evidence ledger holds MCP calls (README does not say it does) |
| C34g | "Local MCP processes receive a small sanitized environment" (README) / "MCP servers … receive their own reduced environments" (SECURITY.md) | `fakemcp` logs its environment variable names (never values) on every launch — the console's registration probes and the build's calls — while both parents hold `CROSSAUDIT_AUDITOR_KEY`/`CROSSAUDIT_GENERATOR_KEY` and the build also a decoy `OPENAI_API_KEY` | no `CROSSAUDIT_*`, `*KEY*`, `*TOKEN*`, `*SECRET*` name and no dummy key value in any launch; the names seen are recorded |

### G. Not testable in this harness

| id | README says | needs |
|---|---|---|
| C32 | The macOS app: DMG download, first-open flow, Keychain-held keys, menu-bar background operation, Environment Doctor UI | a built DMG (`packaging/macos/build_dmg.sh`, PyInstaller, network for the Codex runtime) and a GUI session; the release's DMG is attached to v4.17.0 — can be installed by a person and walked through `docs/UX_TEST_PLAN.md` |
| C33b | Two-repository deployment, live: `pair --apply` creating real repositories, pushing, uploading the auditor secret; the app's device-code GitHub sign-in (**Connect GitHub**) | a GitHub account willing to create repositories (C33a covers plan mode, and `--apply` only against a fake `gh` with local bare repositories) |
| C34b | SSH workstation / Slurm compute; MCP over Streamable HTTP with write-only Keychain bearer tokens and HTTPS/private-network controls; Project Skills managed in the UI | an SSH host and a scheduler; an HTTP MCP endpoint and the macOS Keychain (C34a, C34c–C34g cover local stdio MCP) |
| C35 | The benchmark sentences ("severity, not sight"; precision 100% / recall 2%; "flags fewer correct solutions") | the archived run data (`~/Documents/Crossaudit/study-data/`, present on this machine) and the cross-vendor review they already had; re-running costs money |
| C36 | The auditor catching real defects in real work | live models and a corpus with ground truth: `benchmarks/ai4s/run_auditor.py --live` on a one-seed subset (≈ $10) is the prepared path |

## Scoring

A ref's score is the count of PASS over the testable rows (C01–C31, C33a,
C34a, C34c–C34g from round 2 on), with
PARTIAL and FAIL listed by id and each FAIL carrying the evidence path. "The
project does what it says" is the state in which every testable row is PASS
and every untestable row is honestly marked in the README as a thing the
reader must verify by other means.
