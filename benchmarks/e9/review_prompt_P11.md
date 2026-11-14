Read-only. You reviewed this project before (review_gpt_M1.md, weakness 2 and improvement 3). The author has drafted
E9, an admissibility check by judges outside the construction: crossaudit-harness/benchmarks/e9/PREREGISTRATION-E9.md
and crossaudit-harness/benchmarks/e9/e9.py (it reuses benchmarks/code/icml/e6.py, e1.py and analyse_e6.py). A
development pilot is running (records/e9_dev.jsonl); no held-out E9 call has been made. Before the freeze, check
concisely with file:line: (1) bugs in e9.py, especially order mapping of rule1/rule2 to A/B, the grounding check, the
bootstrap, missing-data bounds and the E9-3 subset analysis; (2) design flaws that would let a reviewer dismiss the
result (judge choice, blinding, leakage of which rule is the benchmark's, the controls as a sensitivity check,
thresholds 50 and 30, multiplicity); (3) anything to add that is cheap and would make the result more convincing.
Separate blocking from optional items. Do not propose human raters.
