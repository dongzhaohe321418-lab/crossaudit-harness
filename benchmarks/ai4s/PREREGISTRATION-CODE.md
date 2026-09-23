# A4S-1 — auditing scientific code (SciCode)

Registered 2026-09-23 **before any model call of this study**, including generation. Amendments are
numbered and committed before the step they govern. Programme: `plan/AI4S-PROGRAM.md` in the paper
repository.

## Question

On toy Python (HumanEval+/MBPP+) the shipped cross-vendor auditor reached 30.0% union recall at
eight readings at 16.0% false positives, and most of what every family missed was failure the
specification never determined. Does that hold on research code, where specifications routinely
leave tolerances, units, conventions and numerical method unstated?

## Substrate and gate

SciCode (Tian et al. 2024), Apache-2.0, from Hugging Face `SciCode1/SciCode` (dev 15 problems / 50
steps with gold code; test 65 problems / 291 steps without) and the benchmark's `test_data.h5`
(1.05 GB, 338 step groups). Execution mirrors the benchmark's own harness
(`eval/inspect_ai/scicode.py`): the program for step *k* is the dependencies, the code of steps
1..*k*, then `targets = process_hdf5_to_tuple(step, n)` and each test with `target = targets[i]`,
in a subprocess with a 600 s timeout. The benchmark's three skipped steps are skipped here too.

**Gate, run before this registration** (`GATE-RESULT.md`): gold code on dev passes 48 of 50 steps;
78.3 depends on wall-clock time by construction, 70.8 is unexplained. Both are excluded from every
stratum.

## Generation

* Generator: `anthropic:claude-haiku-4-5-20251001`, the frozen generator of the earlier studies,
  through the harness's Anthropic provider, default sampling parameters (none sent), max 4,096
  output tokens.
* Protocol: SciCode's *with background* template verbatim (`background_comment_template.txt`), one
  step at a time, earlier steps supplied as this sample's own extracted functions (the benchmark's
  standard setting); for the three skipped steps, the benchmark's own code file is used.
* **Three independent samples per step**, sample *s* carrying its own chain of earlier steps.
* All 80 problems (dev and test).
* Code extraction: the benchmark's `extract_python_script` and `get_function_from_code`.
* Generation halt: **$15**, read from the usage ledger, failing closed.

## Strata

A (sample, step) instance is **correct** if its program passes all of the step's tests, and
**defective** if it fails or times out on any. A step enters either stratum only if at least one
of its three samples passes (**proof of passability in this environment**); steps no sample passes
are counted and excluded, and the bias this introduces (defects on steps the generator can
sometimes solve) is stated wherever the rates are quoted. Instances whose program fails to parse
or define the step's function are discarded, as candidates that fail the visible suite were
discarded before.

**Sampling.** If a stratum exceeds 150 instances, 150 are drawn at seed **20260925**, simple random
at instance level. The unit of resampling is the main problem.

## Auditing

* What the auditor sees: the main problem description, the step's description and background, the
  function header, the dependencies, and the candidate program as `solution.py`. **No tests of any
  kind** — SciCode has no visible/hidden split and this study does not invent one. This departs
  from the EvalPlus design, where a visible suite was shown, and the comparison says so.
* Families, both through the product's `run_audit` with the shipped constitution and ≥ 1 BLOCKER
  to flag: **`cross`** (`openai:gpt-5.6-terra`, shipped) at **K = 8**; **`self`**
  (`anthropic:claude-haiku-4-5-20251001`, the generator) at **K = 8**. Finding texts are archived.
* Audit halt: **$90** cumulative, read from the ledger, failing closed across invocations (the
  per-invocation guard of P4 is not repeated).

## Outcomes

Primary: union recall at K = 8 for `cross` on the defective stratum, with the union false-positive
rate on the correct stratum, both with problem-cluster percentile bootstraps (10,000, seed
20260925). Secondary: the full K ladder and flattening statistic; `self` at K = 8; the paired
`self` − `cross` contrast with exact McNemar and cluster sign-flip; the pooled two-family union on
both strata.

**Residual characterisation.** Defective instances flagged by no reading of either family are
rated under the Act-3 rubric adapted to SciCode: whether the step's prose and background determine
the value the test expects at the tested input, including tolerance, units, conventions and
numerical method (`undetermined` / `determined` / `cannot-tell`), shown the prose, the candidate,
the test inputs and the expected values. Raters: **L1, the research agent that runs this study
(Claude)**, which wrote the rubric and knows the hypotheses; and **`gpt-5.6-luna`**, which audits
nothing in this study. Consensus as in study 21; κ reported.

## Hypotheses and reading, fixed now

* **H1 (descriptive).** `cross` union recall at K = 8 on SciCode is reported beside EvalPlus's
  30.0% as two estimates on two substrates with different designs (no visible tests here); no test
  of their difference is made.
* **H2.** The consensus-undetermined share of the SciCode residual exceeds the EvalPlus share
  (77.2%). Registered reading: supported if the SciCode share's point estimate exceeds 77.2% and its
  cluster interval's lower bound exceeds 50%; **killed** if the lower bound falls below 50%;
  otherwise inconclusive.
* **H3.** The paired `self` − `cross` union-recall contrast at K = 8 is reported with its interval
  and both p values; its sign is not predicted.

What no reading licenses: a claim about scientific code in general (one benchmark, one generator);
calling a flag on a correct instance a mistake (C16 applies); calling a rater's label correct.

## Review

The report goes to cross-vendor review; it enters the paper only when quotable.

## Amendment 1 — the Anthropic route runs through the Claude Code CLI (2026-09-23, before any successful call)

The first generation attempts returned HTTP 400, "credit balance is too low", from the Anthropic
API; no reply was produced and nothing was spent. The API account cannot be topped up by the
agent. The same model, `claude-haiku-4-5-20251001`, is reachable through the Claude Code CLI on
the owner's subscription, so the Anthropic transport changes and nothing else does:

* A shim (`cli_transport.py`) replaces `crossaudit.providers.anthropic.complete` for this study
  only, sending the same system prompt and user prompt to `claude -p --model
  claude-haiku-4-5-20251001 --system-prompt <system> --tools "" --strict-mcp-config` with
  `MAX_THINKING_TOKENS=0` and auto-memory disabled, from an empty working directory. Generation
  and the `self` audit family therefore keep the product's own prompt-building code.
* **What differs from the API route, measured before use:** the CLI adds about 400 tokens of
  context (the working directory, platform, the model's own identity, the date and the owner's
  email address; no project memory, no CLAUDE.md, no MCP tools, verified by having the model
  repeat its context verbatim), and its sampling parameters are the CLI's defaults. Thinking is
  off (0 thinking tokens measured).
* Cost is read from the CLI's reported `total_cost_usd` (list-price equivalent) per call; the
  generation halt of $15 and the audit halt of $90 apply to those figures and fail closed if a
  successful call reports no cost.
* Where the caller passes no system prompt (generation), the CLI rejects an empty one and would
  otherwise substitute its own agent prompt, so the fixed line "You are a helpful assistant." is
  sent. Found on the first CLI attempt, which failed with no reply and no spend.
* The `cross` family (OpenAI) is unaffected.
