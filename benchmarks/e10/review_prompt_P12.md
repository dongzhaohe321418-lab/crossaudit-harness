Read-only. You reviewed this project before (review_gpt_M1.md weakness 4 and improvement 4; review_gpt_P11.md for E9).
The author has drafted E10, an attention control for E6's sentence effect: crossaudit-harness/benchmarks/e10/
PREREGISTRATION-E10.md and e10.py. e10.py reuses E6's frozen stages (benchmarks/code/icml/e6.py stage_audit,
stage_witness, completeness; analyse_e6.py merged_open, level, contrast) by monkeypatching e6's module globals
(set_kind, arm_text, registered_units, configs_for, PROTOCOL, record paths) and freeze.verify. A small development
pilot is running; no held-out E10 call has been made. Check concisely with file:line: (1) bugs, especially whether
the monkeypatching reaches every call site (stage_audit, stage_witness, completeness, analyse_e6.table/merged_open/
population), kind switching inside freeze.verify, the pointer text and neutral_class rule (does any held-out pointer
still leak a rule or signal uncertainty?), scoring of the pointer arm under both contracts, missing-data handling and
the E10-1 verdict; (2) design flaws a reviewer could use to dismiss the result (pointer wording, interleaving,
reusing auditor identities, budget, sample size/power for E10-1); (3) cheap additions. Separate blocking from optional.
