# ---- shared helpers (spliced into every analyse.py by the corpus generator) ----
# Pure standard library. Every function here is deterministic given its inputs;
# the bootstrap draws come from a random.Random seeded on the command line, and
# indices are drawn as int(rng.random() * n) so the stream does not depend on
# the CPython version's randrange implementation.

R_GAS = 8.314462618  # J/(mol K)


def read_csv(text):
    """Rows of a CSV file as dicts of raw strings, in file order."""
    return list(csv.DictReader(io.StringIO(text)))


def column(rows, name, where=None):
    """Float values of one column, optionally only rows where where[0] == where[1]."""
    out = []
    for row in rows:
        if where is not None and row[where[0]] != where[1]:
            continue
        out.append(float(row[name]))
    return out


def mean(x):
    return math.fsum(x) / len(x)


def sd(x):
    """Sample standard deviation (n - 1)."""
    m = mean(x)
    return math.sqrt(math.fsum((v - m) ** 2 for v in x) / (len(x) - 1))


def sd_population(x):
    """Population standard deviation (n): numpy.std's default, ddof=0."""
    m = mean(x)
    return math.sqrt(math.fsum((v - m) ** 2 for v in x) / len(x))


def median(x):
    s = sorted(x)
    mid = len(s) // 2
    return s[mid] if len(s) % 2 else (s[mid - 1] + s[mid]) / 2.0


def linfit(x, y):
    """Ordinary least squares y = slope * x + intercept."""
    mx, my = mean(x), mean(y)
    sxx = math.fsum((a - mx) ** 2 for a in x)
    sxy = math.fsum((a - mx) * (b - my) for a, b in zip(x, y))
    slope = sxy / sxx
    return slope, my - slope * mx


def mae(truth, pred):
    return math.fsum(abs(t - p) for t, p in zip(truth, pred)) / len(truth)


def rmse(truth, pred):
    return math.sqrt(math.fsum((t - p) ** 2 for t, p in zip(truth, pred)) / len(truth))


def r2(truth, pred):
    m = mean(truth)
    ss_res = math.fsum((t - p) ** 2 for t, p in zip(truth, pred))
    ss_tot = math.fsum((t - m) ** 2 for t in truth)
    return 1.0 - ss_res / ss_tot


def _betacf(a, b, x):
    """Continued fraction for the regularised incomplete beta (Lentz)."""
    tiny = 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    d = 1.0 / (d if abs(d) > tiny else tiny)
    h = d
    for m in range(1, 400):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = 1.0 / (d if abs(d) > tiny else tiny)
        c = 1.0 + aa / c
        c = c if abs(c) > tiny else tiny
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < 1e-15:
            break
    return h


def betai(a, b, x):
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
    front = math.exp(lbeta + a * math.log(x) + b * math.log(1.0 - x))
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def t_pvalue_two_sided(t, df):
    return betai(df / 2.0, 0.5, df / (df + t * t))


def t_quantile(p, df):
    """Upper quantile of Student's t by bisection on the two-sided p-value."""
    target = 2.0 * (1.0 - p)
    lo, hi = 0.0, 1000.0
    for _ in range(200):
        mid = (lo + hi) / 2.0
        if t_pvalue_two_sided(mid, df) > target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def welch(a, b):
    """mean(a) - mean(b), its standard error, Welch t and Welch-Satterthwaite df."""
    va, vb = sd(a) ** 2 / len(a), sd(b) ** 2 / len(b)
    diff = mean(a) - mean(b)
    se = math.sqrt(va + vb)
    df = (va + vb) ** 2 / (va ** 2 / (len(a) - 1) + vb ** 2 / (len(b) - 1))
    return diff, se, diff / se, df


def bootstrap_se(rng, n, stat, reps=400):
    """Standard deviation of stat(indices) over reps resamples with replacement.
    stat may return None for a degenerate resample, which is redrawn."""
    values = []
    while len(values) < reps:
        idx = [int(rng.random() * n) for _ in range(n)]
        v = stat(idx)
        if v is not None:
            values.append(v)
    return sd(values)


def first_sig_place(u):
    """Decimal place of the first significant digit (0.023 -> 2, 1.7 -> 0, 23 -> -1)."""
    return -int(math.floor(math.log10(abs(u))))


def round_uncertainty(u):
    """Uncertainty to two significant figures."""
    return round(u, first_sig_place(u) + 1)


def decimals_for(u):
    """Decimals a value may carry under an uncertainty u: one beyond its first
    significant digit, never fewer than zero."""
    return max(0, first_sig_place(u) + 1)


def rounded(v, d):
    return int(round(v)) if d <= 0 else round(v, d)


def sig_decimals(v, figures):
    """Decimals that keep `figures` significant figures of v."""
    return max(0, first_sig_place(v) + figures - 1)


def tolerance(d):
    """Absolute tolerance consistent with rounding to d decimals (0.6 * 10**-d)."""
    if d <= 0:
        return {"abs": 0.5}
    return {"abs": float("6e-%d" % (d + 1))}


def quantity(name, value, unit, source, uncertainty=None):
    q = {"name": name, "value": value, "unit": unit, "source": source}
    if uncertainty is not None:
        q["uncertainty"] = uncertainty
    return q


def derivation(name, method, inputs, d):
    return {"quantity": name, "method": method, "input": inputs, "tolerance": tolerance(d)}


def read_code_version(metadata_text):
    for line in metadata_text.splitlines():
        if line.startswith("code_version:"):
            return line.split(":", 1)[1].strip()
    raise SystemExit("metadata.yml declares no code_version")


def txt_line(q):
    """One human-readable line per quantity; the SUMMARY annotations quote these."""
    unit = "" if q["unit"] == "1" else " " + q["unit"]
    return "%s = %s%s" % (q["name"], json.dumps(q["value"]), unit)


def emit(doc, extra=None):
    """The files this analysis writes, as {relative path: bytes}."""
    out = dict(extra or {})
    out["results.json"] = (json.dumps(doc, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    lines = [txt_line(q) for q in doc["quantities"]]
    out["results.txt"] = ("\n".join(lines) + "\n").encode("utf-8")
    return out


def main(run):
    """Command-line entry: read inputs beside scripts/, write outputs there,
    print results.json."""
    import argparse
    from pathlib import Path
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent.parent
    outputs = run(lambda rel: (root / rel).read_bytes(), args.seed)
    for rel in sorted(outputs):
        (root / rel).write_bytes(outputs[rel])
    sys.stdout.write(outputs["results.json"].decode("utf-8"))
# ---- end shared helpers ----
