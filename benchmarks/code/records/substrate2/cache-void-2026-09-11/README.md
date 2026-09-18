# The VOID run's readings, 2026-09-11 — quarantined, not deleted

These 32 cache files are the original run's readings. Amendment 1 voided them: the visible-test
text shown to the auditor did not parse on any of the 300 tasks.

They are moved out of `cache/` rather than deleted for two reasons. Amendment 2 requires the two
runs to be reported side by side, so the void numbers must remain reproducible. And the audit
driver resumes from `cache/`: with these files in place it reported **"0 to run" for all sixteen
ladder entries**, so a re-run launched without moving them would have re-reported the void
readings as the new run, silently and at no cost, which is how a fake replication happens.

Do not move them back.

## `audit_set.json` is here too, and for a sharper reason

The audit driver freezes its scope to `records/substrate2/audit_set.json` "before the first audit
call" and then **reuses the file if it exists**. The file here was frozen on
2026-09-11T04:56:27Z from the *void* generation: 100 P and 150 C.

The re-run regenerated the candidates, so the same 250 ids now sit in different strata. Under the
new generation they are **92 P, 152 C and 6 F** — six instances that fail their own visible suite
and should never have been audited at all, and eight that were defective and no longer are.

The re-run therefore audited the wrong scope. The readings themselves are sound (250 of 250 on
every arm, no errors), but they cover a set drawn from a superseded generation, and analysing them
against the *new* strata would silently condition the P population on "was defective in both
generations", which is not the population any hypothesis here is about.

The report caught it: `report_substrate2.py` exited 1 with a `KeyError` rather than producing
numbers. `numbers.json` was not regenerated and still describes the void run.

This is the same failure mode as the cache above — a stale artefact silently reused on resume —
and it was missed on the first pass precisely because quarantining the cache *looked* like it had
cleared the way.

## `cost.json` is here too — the third instance of the same trap

`ledger_costs()` freezes the per-project spend to `records/substrate2/cost.json` on first read
and **reuses the file if it exists**. This copy was frozen 2026-09-16 00:19 from the **voided**
run: cross \$18.31, self \$8.10, generation \$1.83, total \$26.41.

The re-run's real spend is different — generation \$1.91, self \$3.69, cross about \$8.28 — so
regenerating the report with this file in place reported the voided run's costs as the re-run's.
Nothing about the rates was wrong; the provenance was.

That makes three artefacts of this class found in one study: the readings cache, `audit_set.json`,
and now `cost.json`. All three live in `records/` because it is committed for provenance, and all
three were reused by existence alone. Amendment 3's generation digest guards the first two; this
one was caught by reading the numbers and noticing the cost did not match what the run actually
spent.

## `self_coverage.json` and `self_coverage_first_read.json` — the fourth and fifth of the class

Both frozen 2026-09-16 00:19, the same moment as `cost.json`, and both from the **voided**
generation: they carry 250 instances where the current scope is 249, and the voided run's denial
counts with them. Like the others they are reused by existence alone, so the report was reading a
superseded snapshot back as if it described the run that had just finished.

`self_coverage_first_read.json` is the worse of the two, because the state it records — the
first-read coverage of an arm that has since been re-run — **cannot be reconstructed**. It is kept
here as history, not restored.

That makes five artefacts of this class in one study: the readings cache, `audit_set.json`,
`cost.json`, and these two. Every one lives in `records/` because that directory is committed for
provenance, and every one is reused on existence rather than on belonging to the current
generation. **Provenance and run-scoping want opposite things from the same directory, and the
code only ever satisfied the first.**
