"""Welch two-sample comparison of a measured response, treated against control.

Reads data/measurements.csv (subject_id, group, response), reports per-group
means, standard deviations and sizes, the difference treated - control with
its Welch 95% confidence interval, Welch t, Welch-Satterthwaite df and the
two-sided p-value (computed from the reported t and df), the control median,
and the treated mean as a ratio of and a percent change from the control
mean. The uncertainty on
the difference is a bootstrap standard error (400 resamples within each group,
seeded by --seed). Writes results.json and results.txt beside scripts/ and
prints results.json. Standard library only.

Usage: python3 scripts/analyse.py --seed <int>
"""
import csv
import io
import json
import math
import random
import sys

#@HELPERS

DATA = "data/measurements.csv"
UNIT = "mmol/L"


def run(read, seed):
    cv = read_code_version(read("metadata.yml").decode("utf-8"))
    src = "%s@%s" % (DATA, cv)
    rows = read_csv(read(DATA).decode("utf-8"))
    ctl = column(rows, "response", ("group", "control"))
    trt = column(rows, "response", ("group", "treated"))
    diff, se, t, df = welch(trt, ctl)
    tq = t_quantile(0.975, df)
    rng = random.Random(seed)

    def boot(_idx):
        a = [trt[int(rng.random() * len(trt))] for _ in trt]
        b = [ctl[int(rng.random() * len(ctl))] for _ in ctl]
        return mean(a) - mean(b)
    unc = round_uncertainty(bootstrap_se(rng, 1, boot))
    d = decimals_for(unc)
    t_rep, df_rep = rounded(t, 3), rounded(df, 2)
    p_rep = rounded(t_pvalue_two_sided(t_rep, df_rep), 4)
    qs = [
        quantity("mean_control", rounded(mean(ctl), 3), UNIT, src),
        quantity("mean_treated", rounded(mean(trt), 3), UNIT, src),
        quantity("sd_control", rounded(sd(ctl), 3), UNIT, src),
        quantity("sd_treated", rounded(sd(trt), 3), UNIT, src),
        quantity("n_control", len(ctl), "1", src),
        quantity("n_treated", len(trt), "1", src),
        quantity("difference", rounded(diff, d), UNIT, src, unc),
        quantity("ci95_low", rounded(diff - tq * se, 3), UNIT, src),
        quantity("ci95_high", rounded(diff + tq * se, 3), UNIT, src),
        quantity("t_statistic", t_rep, "1", src),
        quantity("df", df_rep, "1", src),
        quantity("p_value", p_rep, "1", src),
        quantity("median_control", rounded(median(ctl), 3), UNIT, src),
        quantity("ratio_means", rounded(mean(trt) / mean(ctl), 4), "1", src),
        quantity("change_pct", rounded(100.0 * (mean(trt) - mean(ctl)) / abs(mean(ctl)), 2), "%", src),
    ]
    c = {"column": "group", "equals": "control"}
    tr = {"column": "group", "equals": "treated"}
    a = {"column": "response", "where": tr}
    b = {"column": "response", "where": c}
    ders = [
        derivation("mean_control", "mean", {"file": DATA, "x": "response", "where": c}, 3),
        derivation("mean_treated", "mean", {"file": DATA, "x": "response", "where": tr}, 3),
        derivation("sd_control", "sd", {"file": DATA, "x": "response", "where": c}, 3),
        derivation("sd_treated", "sd", {"file": DATA, "x": "response", "where": tr}, 3),
        derivation("n_control", "count", {"file": DATA, "x": "subject_id", "where": c}, 0),
        derivation("n_treated", "count", {"file": DATA, "x": "subject_id", "where": tr}, 0),
        derivation("difference", "difference", {"file": DATA, "a": a, "b": b}, d),
        derivation("ci95_low", "ci95_low", {"file": DATA, "a": a, "b": b}, 3),
        derivation("ci95_high", "ci95_high", {"file": DATA, "a": a, "b": b}, 3),
        derivation("t_statistic", "welch_t", {"file": DATA, "a": a, "b": b}, 3),
        derivation("df", "welch_df", {"file": DATA, "a": a, "b": b}, 2),
        derivation("p_value", "t_pvalue_two_sided", {"t": "t_statistic", "df": "df"}, 4),
        derivation("median_control", "median", {"file": DATA, "x": "response", "where": c}, 3),
        derivation("ratio_means", "ratio", {"file": DATA, "a": a, "b": b}, 4),
        derivation("change_pct", "percent_change", {"file": DATA, "new": a, "old": b}, 2),
    ]
    claims = [
        {"text": "the difference between groups is significant at the 0.05 level",
         "test": "p_below", "quantity": "p_value", "alpha": 0.05},
        {"text": "the 95% confidence interval for the difference excludes zero",
         "test": "ci_excludes_zero", "low": "ci95_low", "high": "ci95_high"},
    ]
    doc = {"quantities": qs, "stochastic": True, "derivations": ders, "claims": claims}
    return emit(doc)


if __name__ == "__main__":
    main(run)
