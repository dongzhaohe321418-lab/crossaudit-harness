"""Ridge regression of band gap from composition features, group split.

Reads data/compounds.csv and splits.json (train/test ids, held out by chemical
system), fits a ridge model on standardised features (lambda = 1.0, intercept
unpenalised) on the train rows, predicts every row, and compares the test error
with a baseline that predicts the train mean, as a ratio of the two MAEs and as
a percent change from the baseline's. Writes predictions.csv (with the
per-row absolute errors of model and baseline),
results.json and results.txt beside scripts/ and prints results.json.
The uncertainty on mae_test is a bootstrap standard error over test rows
(400 resamples, seeded by --seed). Standard library only.

Usage: python3 scripts/analyse.py --seed <int>
"""
import csv
import io
import json
import math
import random
import sys

#@HELPERS

DATA = "data/compounds.csv"
FEATURES = ["en_mean", "en_diff", "radius_mean_pm", "ionic_fraction"]
TARGET = "bandgap_ev"
LAMBDA = 1.0


def solve(a, b):
    """Gaussian elimination with partial pivoting; a is n x n, b length n."""
    n = len(b)
    m = [list(a[i]) + [b[i]] for i in range(n)]
    for col in range(n):
        piv = max(range(col, n), key=lambda r: abs(m[r][col]))
        m[col], m[piv] = m[piv], m[col]
        for r in range(n):
            if r != col:
                f = m[r][col] / m[col][col]
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    return [m[i][n] / m[i][i] for i in range(n)]


def fit_ridge(xs, ys, lam):
    k = len(xs[0])
    mu = [mean([x[j] for x in xs]) for j in range(k)]
    sg = [sd([x[j] for x in xs]) for j in range(k)]
    zs = [[(x[j] - mu[j]) / sg[j] for j in range(k)] for x in xs]
    ybar = mean(ys)
    ata = [[math.fsum(z[i] * z[j] for z in zs) + (lam if i == j else 0.0)
            for j in range(k)] for i in range(k)]
    atb = [math.fsum(z[i] * (y - ybar) for z, y in zip(zs, ys)) for i in range(k)]
    w = solve(ata, atb)

    def predict(x):
        return ybar + math.fsum(w[j] * (x[j] - mu[j]) / sg[j] for j in range(k))
    return predict


def run(read, seed):
    cv = read_code_version(read("metadata.yml").decode("utf-8"))
    src = "%s@%s" % (DATA, cv)
    rows = read_csv(read(DATA).decode("utf-8"))
    splits = json.loads(read("splits.json").decode("utf-8"))
    train_ids, test_ids = set(splits["train"]), set(splits["test"])
    train = [r for r in rows if r["id"] in train_ids]
    xs = [[float(r[f]) for f in FEATURES] for r in train]
    ys = [float(r[TARGET]) for r in train]
    predict = fit_ridge(xs, ys, LAMBDA)
    baseline = mean(ys)

    lines = ["id,system,split,%s,pred_ev,baseline_ev,abs_err_ev,baseline_abs_err_ev" % TARGET]
    truth, pred, base = {"train": [], "test": []}, {"train": [], "test": []}, {"train": [], "test": []}
    for r in rows:
        split = "train" if r["id"] in train_ids else "test" if r["id"] in test_ids else None
        if split is None:
            continue
        p = predict([float(r[f]) for f in FEATURES])
        g = float(r[TARGET])
        lines.append("%s,%s,%s,%s,%r,%r,%r,%r" % (r["id"], r["system"], split, r[TARGET], p, baseline,
                                                abs(g - p), abs(g - baseline)))
        truth[split].append(float(r[TARGET]))
        pred[split].append(p)
        base[split].append(baseline)

    t, p = truth["test"], pred["test"]
    errs = [abs(a - b) for a, b in zip(t, p)]
    rng = random.Random(seed)
    unc = round_uncertainty(bootstrap_se(rng, len(errs), lambda idx: mean([errs[i] for i in idx])))
    d_mae = decimals_for(unc)
    test = {"column": "split", "equals": "test"}
    train_w = {"column": "split", "equals": "train"}
    qs = [
        quantity("mae_test", rounded(mae(t, p), d_mae), "eV", src, unc),
        quantity("rmse_test", rounded(rmse(t, p), 4), "eV", src),
        quantity("r2_test", rounded(r2(t, p), 4), "1", src),
        quantity("mae_baseline", rounded(mae(t, base["test"]), 4), "eV", src),
        quantity("n_train", len(truth["train"]), "1", src),
        quantity("n_test", len(t), "1", src),
        quantity("error_ratio", rounded(mae(t, p) / mae(t, base["test"]), 4), "1", src),
        quantity("improvement_pct",
                 rounded(100.0 * (mae(t, p) - mae(t, base["test"])) / abs(mae(t, base["test"])), 2),
                 "%", src),
    ]
    pf = "predictions.csv"
    ders = [
        derivation("mae_test", "mae", {"file": pf, "truth": TARGET, "pred": "pred_ev", "where": test}, d_mae),
        derivation("rmse_test", "rmse", {"file": pf, "truth": TARGET, "pred": "pred_ev", "where": test}, 4),
        derivation("r2_test", "r2", {"file": pf, "truth": TARGET, "pred": "pred_ev", "where": test}, 4),
        derivation("mae_baseline", "mae", {"file": pf, "truth": TARGET, "pred": "baseline_ev", "where": test}, 4),
        derivation("n_train", "count", {"file": pf, "x": "id", "where": train_w}, 0),
        derivation("n_test", "count", {"file": pf, "x": "id", "where": test}, 0),
        derivation("error_ratio", "ratio", {"file": pf, "a": "abs_err_ev", "b": "baseline_abs_err_ev",
                                          "where": test}, 4),
        derivation("improvement_pct", "percent_change",
                   {"file": pf, "new": "abs_err_ev", "old": "baseline_abs_err_ev", "where": test}, 2),
    ]
    claims = [{"text": "the model's test MAE is lower than that of the train-mean baseline",
               "test": "less_than", "quantity": "mae_test", "than": "mae_baseline"}]
    doc = {"quantities": qs, "stochastic": True, "derivations": ders, "claims": claims}
    return emit(doc, {"predictions.csv": ("\n".join(lines) + "\n").encode("utf-8")})


if __name__ == "__main__":
    main(run)
