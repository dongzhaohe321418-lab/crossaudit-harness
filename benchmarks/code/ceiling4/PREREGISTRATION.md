# Study 20 — ceiling 4: does the referent rule raise the shipped auditor's ceiling, or only one reading?

Preregistered on `study/ceiling4` **before any model call**, at the commit that adds this file.
Binding: ceiling 1 §0–§1.2, §1.5, Amendments 3–5 (the union-of-K protocol, intervals, the
flattening bar); ceiling 2's arm R (`loop.py`'s `REFERENT_RULE`, verbatim, one reading: +26.8
points on flags for the shipped auditor, exploratory there); study 19 (the same rule lifted
Sonnet 4.6's K = 4 BLOCKER recall 1.8% → 22.7%); `EXPERIMENT_RECORD.md` §9–§10; D153.

## 0. Why

Every ceiling measured so far is a ceiling *under the shipped constitution*. The one lever
that moved recall by more than a few points in any study is the referent rule — telling
the auditor to find what the visible tests do not exercise. Ceiling 2 measured it at one
reading on a 56-instance sub-sample; study 19 measured it on the Anthropic family at K = 4.
Whether it raises the shipped auditor's *saturation* — the fraction of the defect
population it can ever see — or only how fast the curve rises, is the question that decides
whether the ~30% ceiling is the constitution's or the reading's.

## 1. What is run

One new family through the product's provider broker, on ceiling 1's scope (110 P, 150 C,
the frozen study-2 solutions, the same audit path):

| family | detector | draws |
|---|---|---|
| `cross-R` | `holistic` audit, `openai:gpt-5.6-terra`, the shipped constitution + `REFERENT_RULE` | **K = 8** |

`cross` (K = 8, ceiling 1) is the comparator, reused. Readings are cached per
`(kind, route, draw, instance)` under `records/ceiling4/cache/`; every finding's text is
archived in the run directory (never the repository), as study 19 did, so the naming and
recognition questions can be adjudicated on a draw if the results warrant it (§4).

## 2. Hypotheses, sign fixed

* **H20a (primary).** Union BLOCKER recall at K = 8 on P, `cross-R` − `cross`, paired per
  instance, problem-cluster bootstrap (seed 20260913, 10,000 resamples), Tango and
  grid-unconditional beside it: positive with the cluster interval excluding zero. Sign:
  positive means the rule raises what eight readings reach.
* **H20b (the ceiling, not the slope).** The fitted asymptote A(`cross-R`) − A(`cross`)
  (ceiling 1 §1.2's form, constrained), cluster bootstrap over problems refitting inside
  each resample; and the flattening bar at K = 8 for `cross-R` (gain K = 7 → 8 ≤ 1.0
  point). If `cross-R` has not flattened at K = 8 its asymptote is an extrapolation and is
  reported as one; the raw K = 8 union difference (H20a) is then the sturdier number, as
  ceiling 1 found.
* **H20c (the cost).** Union FP at K = 8 on C, `cross-R` − `cross`, with its intervals; and
  `cross-R`'s single-draw FP against the product bar (6.7%).
* **H20d (the residual).** The residual across all measured families (56 of 110 after study
  18) with `cross-R` added: how many leave it and of which of ceiling 1's categories. Sign not
  fixed; the prior from study 19's R is small (3 of 56).

Kill for "the rule raises the ceiling": H20a's interval includes zero, or H20a is positive
but `cross-R`'s eight-reading union is within `cross`'s cluster interval at K = 8
[19.8, 40.7] — the rule then moves one reading, not the ceiling.

## 3. Secondaries

Per-K curves with cluster intervals; `mixed` (K/2 `cross` + K/2 `cross-R`) against each alone
at matched totals; the any-finding rule for both families (preregistered here as a
secondary, a flag rate, not a defect-naming rate); reply-format counts and ledger cost.

## 4. Adjudication, conditional

If H20a is positive, draw 1 of `cross-R` on P is adjudicated as study 19's H19d was (the
naming question, then the recognition question), L1 the author and L2 a different vendor's
model, blind to metadata; if H20a is not positive no adjudication is run and the finding
texts stay archived unread.

## 5. Budget, ladder, stopping

`cross` cost $0.95–1.68 per 260-reading draw in ceiling 1; the rule lengthens replies, so
≈ $2.5 per draw; ladder `cross-R` draws 1–8 in order, cap **$30**; stop at the cap and
report the K reached with K_common = min(K, 8).

## 6. Boundary

Unchanged: the hidden suite reaches no prompt, check or model; the audit path is the
product's; `src/` is not touched; the generator setting is ceiling 1's cross family's.

## Amendment 1 — 2026-09-10, during `cross-R` draw 1, before any result of it was read

The paper's gap analysis (scratchpad memo, 2026-09-10) ranks first an adjudication of the
SHIPPED auditor's findings — has anyone checked that `cross`'s 30.0% flag rate names the
defects? — and the archive cannot support it: ceiling 1's harness dropped the finding
texts before caching, and no `cross` reading with its texts exists. **Added to the end of
this study's ladder: one reading of `cross-T`** — the shipped constitution unchanged, the
shipped cross auditor, texts archived, 260 instances (≈ $1.5, inside the cap). It enters no
H20 contrast (H20a–d use ceiling 1's `cross` draws as before). §4's conditional adjudication
becomes unconditional for `cross-T`'s draw: its P findings are adjudicated with study 19's
naming and recognition questions (L1 the author, L2 a different vendor's model, blind to
metadata), and `cross-R`'s draw 1 is adjudicated beside it whether or not H20a is positive.
The primary rate is "P instances with a defect-asserting finding / 110" for `cross-T`,
with both intervals; the kill named by the memo — below 20 of 110, the headline becomes
"flag rate 30.0%, defect-naming recall X%" — is adopted here for that rate.
