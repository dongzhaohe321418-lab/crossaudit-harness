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
