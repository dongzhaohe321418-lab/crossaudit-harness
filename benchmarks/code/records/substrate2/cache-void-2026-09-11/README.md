# The VOID run's readings, 2026-09-11 — quarantined, not deleted

These 32 cache files are the original run's readings. Amendment 1 voided them: the visible-test
text shown to the auditor did not parse on any of the 300 tasks.

They are moved out of `cache/` rather than deleted for two reasons. Amendment 2 requires the two
runs to be reported side by side, so the void numbers must remain reproducible. And the audit
driver resumes from `cache/`: with these files in place it reported **"0 to run" for all sixteen
ladder entries**, so a re-run launched without moving them would have re-reported the void
readings as the new run, silently and at no cost, which is how a fake replication happens.

Do not move them back.
