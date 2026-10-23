# Cross-vendor review — science-ai4s pack v2 (bench/ai4s-pack-v2), round 2

**Reviewer:** OpenAI `gpt-5.6-terra` through Codex CLI 0.151.0 (`codex exec`, sandbox `workspace-write`, the subscription route; no API spend).
**Tree reviewed:** `bench/ai4s-pack-v2` at c9c4a83 (the six round-1 repairs, a6c64d5, and Amendment 5), in a detached worktree.
**Brief:** the round-1 text, the repair diff d909a43..c9c4a83, the original pack diff, DESIGN.md Amendment 5; reproduce each round-1 input, probe for new fail-open or false-block shapes, check the amendment's accuracy. **Run by:** the Claude lead, 2026-10-23. **Verdict:** MERGE, one P3 (a DESIGN.md sentence about NaN/Infinity, corrected in the commit that records this review).

The reviewer's text follows verbatim.

---

Findings:

- **P3** — [benchmarks/ai4s/DESIGN.md:259](/private/tmp/claude-501/-Users-ericdong-Claude/dcfd629a-77dc-4e36-bcb9-0f162d0ec0ad/scratchpad/reviews/tree-v2r2/benchmarks/ai4s/DESIGN.md:259)  
  The description says NaN/Infinity “fails to parse.” This parser accepts Python’s non-standard JSON constants; `{"value": NaN}` parses, then `numeric_validity` blocks it.  
  Reproduction: a `results.json` quantity with `value: NaN` produces `CA-NUM-005`, not a schema parse failure.  
  Suggested fix: say strict JSON forbids these literals, but the current parser accepts and explicitly blocks them. This does not affect fail-closed behavior.

Round-1 reproductions against repaired code:

1. Empty `where` selection: **refused** — `CA-DERIV-001`: “the where filter … selects no rows … a derivation over zero rows cannot be verified”.
2. `uncommitted: true` with no file / numeric file, and non-boolean `uncommitted`: **refused** — `CA-DERIV-001`: “an uncommitted file must still be named” / “must be true or false”.
3. Duplicate range `max`: **refused** — `CA-PHYS-001`: “repeats a JSON key ('max' in [0]) … ambiguous”.
4. Range typo `maximum`: **refused** — `CA-PHYS-001`: “has a key the range format does not take ('maximum')”.
5. Split typo `group_colum`: **refused** — `CA-ML-001`: “has a key the split format does not take ('group_colum')”.
6. Sibling `../e2/data.csv`: **refused** — `CA-DERIV-001`: “resolves to … outside … the directory holding this results.json”.

Additional probes: nonexistent `where` column, NaN/Infinity/`1e309` CSV cells, malformed `val`, BOM+CRLF CSV, and nested duplicate keys all behaved fail-closed where invalid; BOM+CRLF correctly verified. A present file marked `uncommitted: true` is recomputed rather than advisory. The committed-tree materialization rejects symlinks before checks receive the `path -> bytes` map.

Amendment 5 accurately describes the six repairs. I regenerated the full corpus: 2,460 JSON files had zero duplicate keys, path climbs, unknown split keys, simultaneous `val`/`validation`, empty `where` lists, or malformed uncommitted declarations. Re-running both profiles produced 4,120 rows, zero errors, byte-identical repeats, and zero semantic differences from the committed v2 rows (excluding wall time).

Read in full: `AGENTS.md`; `src/crossaudit/dcl/ai4s.py`. Reviewed all repair hunks in `tests/test_dcl_ai4s.py`, Amendment 5, the prior review, framework/quantity interfaces, and corpus runner/tests.

Tests run:

```sh
env -u HTTP_PROXY -u http_proxy -u HTTPS_PROXY -u https_proxy -u ALL_PROXY -u all_proxy PYTHONPATH=src PYTHONUTF8=1 /Users/ericdong/Claude/crossaudit-harness/.venv/bin/python -m pytest -q --timeout=30 tests/test_dcl_ai4s.py benchmarks/ai4s/tests
```

**986 passed**.

VERDICT: MERGE