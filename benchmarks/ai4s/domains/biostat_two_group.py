"""biostat_two_group: Welch comparison of fasting glucose, treated vs control.

Responses are Gaussian with a known group difference. The clean template is
drawn until the two-sided p-value is in [0.0005, 0.04), so the declared
'significant at 0.05' claim is true on every seed (a rejection step over
synthetic draws, recorded here so nobody reads it as a power statement).
Honest boundary: no subjects, no design, just two Gaussian samples.
"""
from __future__ import annotations

import sys

from . import Instance, assemble, csv_bytes, gauss, new_instance, qvalue, rerun_analysis, shuffled, uniform

NAME = "biostat_two_group"
SLUG = "glucose-trial"
PROJECT = "Treatment effect on fasting glucose"
INPUTS = ["data/measurements.csv"]
METHOD = "Welch's unequal-variance two-sample t-test, two-sided; Welch 95% CI for treated minus control"
TASK = """\
# Task

Compare fasting glucose (mmol/L) between the treated and control groups in
data/measurements.csv. Report each group's mean, SD and size, the difference
(treated minus control) with its 95% confidence interval, the t statistic,
degrees of freedom and two-sided p-value, and state whether the difference is
significant at the 0.05 level.
"""
DOMAIN_RULES = """\
### CA-STAT-001
**BLOCKER.** The test named in the summary is the test the metadata declares,
and every subject in the committed data is analysed in the group recorded for it.
"""
U = "mmol/L"
RANGES = [
    {"name": "mean_*", "unit": U, "min": 0, "max": 50},
    {"name": "sd_*", "unit": U, "min": 0, "max": 20},
    {"name": "n_*", "unit": "1", "min": 2},
    {"name": "difference", "unit": U, "min": -50, "max": 50},
    {"name": "ci95_*", "unit": U, "min": -50, "max": 50},
    {"name": "t_statistic", "unit": "1", "min": -1000, "max": 1000},
    {"name": "df", "unit": "1", "min": 1, "max": 10000},
    {"name": "p_value", "unit": "1", "min": 0, "max": 1},
]


def _data(rng, prm, effect_sd):
    ctl = [round(gauss(rng, prm["mu"], prm["sd"]), 2) for _ in range(prm["n_c"])]
    trt = [round(gauss(rng, prm["mu"] + effect_sd * prm["sd"], prm["sd"] * prm["ratio"]), 2)
           for _ in range(prm["n_t"])]
    rows = [("control", v) for v in ctl] + [("treated", v) for v in trt]
    rows = shuffled(rng, rows)
    return csv_bytes(["subject_id", "group", "response"],
                     [["s%03d" % (i + 1), g, "%.2f" % v] for i, (g, v) in enumerate(rows)])


def build_clean(rng, seed) -> Instance:
    mod = sys.modules[__name__]
    inst = new_instance(mod, seed, rng)
    prm = {"mu": uniform(rng, 5.2, 6.2), "sd": uniform(rng, 0.6, 0.9), "ratio": uniform(rng, 0.85, 1.2),
           "n_c": 18 + int(rng.random() * 7), "n_t": 18 + int(rng.random() * 7)}
    effect = -uniform(rng, 0.8, 1.1)
    inst.params = prm
    for _attempt in range(200):
        assemble(mod, inst, {"data/measurements.csv": _data(rng, prm, effect)})
        p = qvalue(inst.results(), "p_value")
        if 0.0005 <= p < 0.04 and qvalue(inst.results(), "difference") < 0:
            return inst
    raise RuntimeError("no significant biostat draw")


def regenerate(inst: Instance, variant: str, rng) -> Instance | None:
    """significance_overclaim: response redrawn with a near-zero effect until
    0.05 < p < 0.12 (a marginal result written up as significant);
    ci_claim_false: redrawn with zero effect until p > 0.3 (the interval
    clearly straddles zero). Everything is recomputed by analyse.py and the
    claims are left in place, so they are false against the committed data.
    p < 0.05 and a Welch CI excluding zero are the same event, so both
    variants falsify both declared claims."""
    if variant == "significance_overclaim":
        effect, ok = -0.45, (lambda p: 0.05 < p < 0.12)
    elif variant == "ci_claim_false":
        effect, ok = 0.0, (lambda p: p > 0.3)
    else:
        return None
    for _attempt in range(500):
        new = inst.copy()
        new.files[new.path("data/measurements.csv")] = _data(rng, inst.params, effect)
        rerun_analysis(new)
        if ok(qvalue(new.results(), "p_value")):
            return new
    raise RuntimeError("could not falsify the biostat claim")


def wrong_rows(inst: Instance):
    """mean_treated recomputed on the CONTROL rows."""
    import csv
    import io
    vals = [float(r["response"]) for r in csv.DictReader(io.StringIO(inst.text("data/measurements.csv")))
            if r["group"] == "control"]
    return [("mean_treated", sum(vals) / len(vals))]


def summary(p, inst: Instance) -> str:
    unc = p.unc("difference")
    word = "lower" if p.q["difference"]["value"] < 0 else "higher"
    return (
        "# Effect of treatment on fasting glucose\n\n"
        f"Fasting glucose was measured in {p.n('n_control')} control and {p.n('n_treated')} "
        f"treated subjects. The mean was {p.n('mean_control')} (SD {p.n('sd_control')}) in the "
        f"control group and {p.n('mean_treated')} (SD {p.n('sd_treated')}) in the treated group, "
        f"so the mean response was {word} in the treated group: the difference (treated minus "
        f"control) is {p.n('difference')} (bootstrap standard error {unc} mmol/L), with a 95% CI "
        f"from {p.n('ci95_low')} to {p.n('ci95_high')}.\n\n"
        f"Welch's unequal-variance t-test gives t = {p.n('t_statistic')} with {p.n('df')} degrees "
        f"of freedom and p = {p.n('p_value')}. The difference is statistically significant at the "
        "0.05 level, and the 95% confidence interval excludes zero.\n")


SPEC = {
    "d03": ("difference", "mg/dL"),
    "d07": "sd_control",
    "d08": {"above_max": ("p_value", 1.4), "below_min": ("df", 0.4)},
    "d10_targets": ["mean_treated", "mean_control", "difference"],
    "wrong_rows": wrong_rows,
    "n_quantity": "n_treated",
    "direction": ("mean response was lower in", "mean response was higher in"),
    "method": ("Welch's unequal-variance t-test", "Student's pooled-variance t-test"),
    "d13": ["significance_overclaim", "ci_claim_false"],
    "has_split": False,
}
