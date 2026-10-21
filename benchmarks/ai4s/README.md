# AI4S audit test set

A synthetic, licence-free, stdlib-only evaluation corpus for the deterministic
check layer (DCL) of CrossAudit, aimed at the defect classes that matter in
AI-for-science deliverables, and the measurement of a declaration-based check
pack (`science-ai4s`) against the shipped `science` profile.

- `DESIGN.md` — the preregistration: starting point, hypotheses, corpus
  contract, defect taxonomy, check-pack contract, analysis plan, limitations.
  Read it first.
- `taxonomy.json` — the 17 defect classes, machine-readable, with per-variant
  expectations.
- `RESULTS.md` — rendered from `records/run-*/numbers.json`; the numbers the
  design committed to, as they came out.
- `generate.py`, `domains/`, `planted.py` — the corpus generator: six
  scientific domains, each with a committed stdlib `scripts/analyse.py` that
  the generator itself runs to produce `results.json`, and 41 single-fault
  planters.
- `run_checks.py`, `score.py`, `report.py` — the deterministic-layer runner,
  the scorer (Wilson intervals, cluster bootstrap over templates, coverage
  simulation) and the report renderer.
- `run_auditor.py` — the model-layer runner. Dry-run by default; the live
  path refuses to spend money without a key, a `--max-usd` cap and an
  explicit acceptance flag.
- `tests/` — the corpus's own consistency tests (clean controls pass the
  shipped profile with zero findings; every planted edit is where the
  manifest says; every `analyse.py` reproduces its own `results.json`) and
  the scorer's tests (interval values, bootstrap coverage, prose-to-numbers
  binding).

## Reproduce

```bash
cd benchmarks/ai4s
export PYTHONPATH=../../src
python generate.py --seed 20261021 --out records/corpus
python run_checks.py --corpus records/corpus --profiles science,science-ai4s \
    --out records/run-2026-10-21 --repeat 2
python score.py records/run-2026-10-21
python report.py records/run-2026-10-21 > RESULTS.md
python -m pytest -q tests
```

No network, no credentials, no third-party packages. The corpus directory is
regenerated and gitignored. The committed record, per
`benchmarks/EXPERIMENT_RECORD.md` §3, is `records/manifest.jsonl.gz` (one row
per instance with the sha256 of every file; its uncompressed sha256 is in each
run's `run.json`), and under each `records/run-*/`: `rows.jsonl.gz` (one row
per instance per profile), `numbers.json`, `run.json`, `checks_contracts.json`
and, where the lead recorded them, `DEVIATIONS.md`. `score.py` reads the
uncompressed `rows.jsonl`, so to re-score a committed run gunzip it first, or
regenerate the run in 20 s with the commands above. The
`records/run-2026-10-21-exploratory-x30/` directory is a post-hoc run at 30
seeds per domain, labelled exploratory in `RESULTS.md` and `DEVIATIONS.md`.

## What the corpus is not

It is synthetic and single-fault, it measures the deterministic rung only, and
its declarations are written the way a compliant generator would write them.
`DESIGN.md` §6 states each limitation; `RESULTS.md` repeats them beside the
numbers.
