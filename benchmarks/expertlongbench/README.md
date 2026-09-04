# ExpertLongBench × CrossAudit

Does the dual-source audit **demonstrably** improve the accuracy of what CrossAudit
produces? This directory is the measurement, not the assertion.

It runs two arms over the same expert-level tasks with the same generator model, scores
both with a faithful reimplementation of the benchmark's own CLEAR metric, and reports the
paired difference:

- **arm A — single model.** One generator call with the task input. No audit.
- **arm B — CrossAudit.** The product's real `build` loop: generator → deterministic checks
  → cross-vendor auditor → bounded revision, same generator model and settings as arm A.

A second question rides along, because it needs the same run: for every BLOCKER the auditor
raised in arm B, was the thing it objected to *actually* wrong? That confirmation rate is
what decision **D142** deferred `authority.lone_model_blocker`'s default on.

## Files

| file | what it is |
|---|---|
| `NOTES.md` | The paper's method, transcribed with section citations. **Read this first.** The scorer is checked against it, not against a recollection of it. |
| `fetch.py` | Downloads the seven public tasks, pins each by sha256 and row count, fails loudly on drift. |
| `manifest.json` | The pins. Digests, row counts and rubric item names only — no dataset text. |
| `tasks.py` | Per-task rubric item descriptions and the model prompt, transcribed verbatim from the paper's Appendix B (they are not in the dataset). |
| `clear.py` | CLEAR: checklist mapping, bidirectional containment judging, precision / recall / accuracy / F1. |
| `provider.py` | Binds CLEAR's model seam to CrossAudit's own provider layer, so mapper and judge calls are configured, retried and metered like any other call. |
| `run.py` | The two-arm runner. |
| `report.py` | Study 1's two numbers: paired accuracy difference, and the BLOCKER confirmation rate. |
| `report2.py` | Study 2's numbers: the paired **within-instance** pre/post-revision difference, and the auditor's **recall against ground truth**. Joins several run directories by arm label. |
| `tests/` | Unit tests for the scorer, over hand-built cases whose F1 is arithmetic. |
| `RESULTS.md` | Study 1 (n=12). What actually happened, sample size in the headline. |
| `RESULTS-2.md` | Study 2 (n=40 + two 10-instance arms). Why the auditor was silent, and whether revision helps. |

## Running it

```sh
export PYTHONPATH="$(git rev-parse --show-toplevel)/src"
python benchmarks/expertlongbench/fetch.py            # needs a proxy on some networks
python -m pytest benchmarks/expertlongbench/tests -q  # offline; no keys needed
python benchmarks/expertlongbench/run.py --task T03MaterialSEG --n 10 --seed 20260904
python benchmarks/expertlongbench/report.py benchmarks/expertlongbench/runs/<run-id>
```

`--out`, if given, must be an **absolute** path: the loop chdirs into each scratch project,
so a relative run directory makes the product resolve its own config root against the wrong
place. `--resume` continues a run that was interrupted, skipping samples already recorded.
`RESULTS-2.md` has the exact three commands that produced study 2.

The unit tests are not in the repo's default `testpaths`; run them by path as above.

## Data licence — please read before using this

The ExpertLongBench corpus is **CC BY-NC-SA 4.0**: attribution required, **non-commercial
use only**, share-alike on adaptations. It is *not* redistributed here. `fetch.py`
downloads it from Hugging Face into `data/`, which is gitignored, and the only thing
committed is `manifest.json` — filenames, sha256 digests, row counts and rubric item names.
No dataset row, no `input` text, no reference content, and no model output (which quotes
the input) may ever be committed; run directories are gitignored for the same reason.

Because of the NonCommercial term, this directory is a research artefact only. It lives
outside `src/crossaudit/`, is excluded from the built wheel, and must not be wired into a
paid product surface or used in marketing material.

> Jie Ruan, Inderjeet Jayakumar Nair, Shuyang Cao, Amy Liu, Sheza Munir, Micah
> Pollens-Dempsey, et al. *ExpertLongBench: Benchmarking Language Models on Expert-Level
> Long-Form Generation Tasks with Structured Checklists.* arXiv:2506.01241, 2025.

## Honesty rules for anyone extending this

1. **Do not tune arm B's prompts after seeing scores.** If anything in either arm changes
   mid-study, the study restarts and `RESULTS.md` says so.
2. **A negative result is the point.** If the loop does not beat the single model, that goes
   in the first sentence of the results file, not in a footnote, and it is not re-run until
   it flips. Both studies so far are negative results and both say so in their first
   sentence.
3. **Every approximation of the paper's method is listed** under "Deviations from CLEAR" in
   `RESULTS.md`. The authors released no evaluation code, so absolute scores are not
   comparable to their leaderboard; the paired within-scorer comparison is.
