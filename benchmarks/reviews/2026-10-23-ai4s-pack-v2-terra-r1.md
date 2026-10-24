# Cross-vendor review — science-ai4s pack v2 (bench/ai4s-pack-v2), round 1

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `bench/ai4s-pack-v2` at d909a43, in a detached worktree (the reviewer reports the tree stayed unmodified).
**Brief:** AGENTS.md §0 and §1; the diff `main..d909a43` for `src/` and `tests/`; DESIGN.md Amendments 1–4 and RESULTS.md; the suite command. **Run by:** the Claude lead, 2026-10-23. **Verdict:** DO NOT MERGE (five P1, one P2). The repairs are recorded in DESIGN.md Amendment 5 and the second round in `2026-10-23-ai4s-pack-v2-terra-r2.md`.

The reviewer's text follows verbatim.
---

Findings:

1. **P1** — `src/crossaudit/dcl/ai4s.py:953-981`  
   An empty `where` match can verify `count == 0` and `sum == 0`, rather than refusing an unverifiable derivation.  
   Reproduction: CSV `split,x\ntest,999\n`; declare `sum` of `x` with `where: {"column":"split","equals":"missing"}` and report `0`. The check returns no findings and `PASS`.  
   `tests/test_dcl_ai4s.py:408-416` actively encodes this false pass for `count`; it would not catch a fix requiring matches.  
   Fix: after every declared filter, reject an empty selected row set with CA-DERIV-001 before method dispatch (including `count` and `sum`).

2. **P1** — `src/crossaudit/dcl/ai4s.py:1110, 1149-1159`  
   `uncommitted: true` without a usable `file` silently becomes an advisory and allows `PASS`.  
   Reproduction: `{"quantity":"out","method":"mean","input":{"x":"x","uncommitted":true}}` for a reported value of `0` returns only CA-DERIV-002, with “file declared uncommitted (None)”. A non-string `file` has the same result; a non-boolean `uncommitted` is silently ignored.  
   Fix: require `uncommitted` to be boolean, and require an explicit non-empty string `file` before CA-DERIV-002 is possible; otherwise raise CA-DERIV-001.

3. **P1** — `src/crossaudit/dcl/ai4s.py:170, 301, 1211`  
   All new JSON declaration readers accept duplicate object keys, with Python silently retaining the last value. That makes ambiguous declarations pass.  
   Reproduction: range block `[{"name":"p","unit":"1","max":0.05,"max":1}]` with quantity `p=0.9` passes `range_rules`; the intended first cap is discarded. Duplicate `value`, `where`, or split keys have the same ambiguity.  
   Fix: use an `object_pairs_hook` that rejects duplicate names for `results.json`, range blocks, and `splits.json`, emitting the relevant blocker rather than skipping or accepting the file.

4. **P1** — `src/crossaudit/dcl/ai4s.py:313-330`  
   Range entries ignore unknown fields. A typo can erase a bound without a finding.  
   Reproduction: `[{"name":"p","unit":"1","maximum":0.05}]` with `p=0.9` passes.  
   Fix: require each entry’s keys to be exactly a subset of `{name, unit, min, max}`; reject extras under CA-PHYS-001. Add a regression test for `maximum`.

5. **P1** — `src/crossaudit/dcl/ai4s.py:1217-1238`  
   `splits.json` ignores unknown keys, so a misspelled optional `group_column` disables group-leakage detection.  
   Reproduction: `{"data":"data.csv","id_column":"id","group_colum":"system","train":["a"],"test":["b"]}` with both rows in group `G` passes.  
   Fix: reject keys outside `{data,id_column,group_column,train,test,val,validation}`; also reject simultaneous `val` and `validation` as ambiguous.

6. **P2** — `src/crossaudit/dcl/ai4s.py:947-952`; `src/crossaudit/scaffold/templates/AI4S_DECLARATIONS_SKILL.md:18-20`  
   The shipped skill promises paths “never `../…`”, but the implementation accepts a sibling experiment’s committed CSV.  
   Reproduction: from `experiments/e1/results.json`, `file: "../e2/data.csv"` successfully verifies if that file is in scope. The existing path test only uses nonexistent escaped paths.  
   Fix: either reject normalized paths outside the results/splits directory, or revise the skill and contract to state that any in-scope path is accepted. The former matches the current documentation.

Verified:

- Read in full: supplied `AGENTS.md`; `src/crossaudit/dcl/ai4s.py`; `src/crossaudit/dcl/profiles.py`; `src/crossaudit/scaffold/templates/AI4S_DECLARATIONS_SKILL.md`; `tests/test_dcl_ai4s.py`.
- Reviewed the changed sections of `framework.py`, `scaffold/__init__.py`, `test_chat_list.py`, and `test_number_source_check.py`; `git diff --check` was clean. Working tree remained unmodified.
- Checked the new profile leaves `science` unchanged. The changed unknown-profile denial remains covered by the existing generic Chinese translation; I found no new `Denial`-translation gap.
- Ran:
  - `env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_dcl_ai4s.py` → **883 passed**.
  - Focused related files with the same environment → **1267 passed, 1 failed, 4 skipped**; the failure was sandbox `PermissionError` binding loopback.
  - Prescribed full command → **4795 passed, 31 failed, 78 errors, 8 skipped** in 396.57s. The errors and demonstrated integration failures are dominated by the sandbox forbidding localhost socket binds; it does not explain the six reproduced AI4S defects.

VERDICT: DO NOT MERGE — multiple declared inputs silently pass instead of fail-closing.