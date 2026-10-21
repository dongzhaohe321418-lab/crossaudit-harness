"""Render ``RESULTS.md`` for the AI4S study from ``numbers.json`` and nothing else.

    PYTHONPATH=../../src python report.py records/run-2026-10-21 > RESULTS.md
    PYTHONPATH=../../src python report.py records/run-2026-10-21 --out RESULTS.md

No statistic is computed here. Every number in the prose is read from
``numbers.json`` and printed through ``fmt``; the H1/H2 decisions are the
booleans ``score.py`` wrote under ``claims``; the document carries
``<!-- numbers: <sha256 of numbers.json> -->`` so ``tests/test_report.py`` can
bind the prose to the exact file it came from and check that every number in
it is a formatted value of that file.

Honest boundary: the report is only as right as ``numbers.json``. It states the
coverage status of the primary interval as recorded (``primary.coverage_checked``)
and does not re-derive it, and its Limitations section is a fixed restatement
of DESIGN §6, not an analysis of this run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

STYLES = ("int", "p", "pct", "pct0", "ms", "raw")


def fmt(value, style: str = "raw") -> str:
    """The one number formatter. ``tests/test_report.py`` uses it to bind prose to numbers.

    int  -> 12          p    -> 0.667        pct -> 66.7%
    pct0 -> 67%         ms   -> 3.03         raw -> 0.95 / 2000
    """
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if style == "int":
        return str(int(round(value)))
    if style == "p":
        return f"{value:.3f}"
    if style == "pct":
        return f"{100 * value:.1f}%"
    if style == "pct0":
        return f"{100 * value:.0f}%"
    if style == "ms":
        return f"{value:.2f}"
    if style == "raw":
        return str(value) if isinstance(value, int) else f"{value:g}"
    raise ValueError(style)


def rate_cell(c: dict | None) -> str:
    """``k/n (rate [low, high])`` — a rate never travels without its count and interval."""
    if not c or not c.get("n"):
        return "n/a (n = 0)" if c else "not run"
    return (f"{fmt(c['k'], 'int')}/{fmt(c['n'], 'int')} ({fmt(c['rate'], 'pct')} "
            f"[{fmt(c['wilson_low'], 'pct')}, {fmt(c['wilson_high'], 'pct')}])")


def _fired(codes: dict | None) -> str:
    if codes is None:
        return "not run"
    if not codes:
        return "nothing"
    return ", ".join(f"`{code}` ×{fmt(n, 'int')}" for code, n in codes.items())


def _class_key(c: str) -> tuple:
    return (len(c), c)


def render(numbers: dict, numbers_sha256: str) -> str:
    prof = numbers["profiles"]
    shipped, extended = prof.get("shipped"), prof.get("extended")
    conf = fmt(numbers["confidence"], "pct0")
    L: list[str] = []
    w = L.append

    w("# AI4S audit test set — results")
    w("")
    w(f"<!-- numbers: {numbers_sha256} -->")
    w("")
    w("Rendered by `report.py` from `numbers.json` only; the design and the "
      "preregistered claims are in `DESIGN.md`. Every rate below is quoted as "
      f"count/n with its {conf} Wilson score interval.")
    w("")

    # ---------------------------------------------------------------- claims
    w("## Claims")
    w("")
    h1 = numbers["claims"]["H1"]
    n_classes = (numbers["recall"]["class_avg"].get(shipped) or {}).get("n_classes")
    if h1["decidable"]:
        verdict = "holds" if h1["holds"] else "does not hold"
        w(f"- **H1 {verdict} on this corpus.** The shipped profile `{shipped}` has "
          f"class-averaged deterministic recall {fmt(h1['value'], 'p')} over "
          f"{fmt(n_classes, 'int')} classes; H1 requires below {fmt(h1['threshold'], 'p')}.")
    else:
        w("- **H1 cannot be decided on this run:** the shipped profile produced no "
          "planted rows.")
    h2 = numbers["claims"]["H2"]
    if h2["decidable"]:
        verdict = "holds" if h2["holds"] else "does not hold"
        w(f"- **H2 {verdict} on this corpus.** Extended minus shipped class-averaged "
          f"recall is {fmt(h2['delta'], 'p')} (required at least "
          f"{fmt(h2['delta_threshold'], 'p')}), and the extended profile's false-block "
          f"Wilson upper bound is {fmt(h2['false_block_upper'], 'pct')} (required at most "
          f"{fmt(h2['false_block_upper_threshold'], 'pct')}).")
        if h2.get("ci_low_above_zero") is not None:
            above = "is" if h2["ci_low_above_zero"] else "is not"
            w(f"  Secondary condition, stated alongside and not part of the preregistered "
              f"decision rule: the bootstrap interval's lower bound "
              f"{fmt(h2['ci_low'], 'p')} {above} above 0.")
    else:
        w(f"- **H2 cannot be decided on this run:** it needs both `science` and "
          f"`science-ai4s`; the run had `{', '.join(prof['run']) or 'none'}`"
          + (f" and could not resolve `{', '.join(prof['unknown'])}`" if prof.get("unknown") else "")
          + " (see Deviations).")
    w("")

    # ---------------------------------------------------------------- primary
    w("## Primary outcome")
    w("")
    pr = numbers["primary"]
    if pr.get("available"):
        w(f"Extended (`{extended}`) minus shipped (`{shipped}`) class-averaged recall: "
          f"**{fmt(pr['delta'], 'p')}**, {conf} cluster-bootstrap percentile interval "
          f"[{fmt(pr['ci_low'], 'p')}, {fmt(pr['ci_high'], 'p')}] for the class-averaged "
          f"recall difference, resampling {fmt(pr['clusters'], 'int')} templates "
          f"(`pair_id`) with replacement, {fmt(pr['resamples'], 'int')} resamples, "
          f"percentiles {fmt(pr['percentiles'][0])}/{fmt(pr['percentiles'][1])}, "
          f"seed {fmt(pr['seed'], 'int')}.")
    else:
        w(f"Not computed: {pr.get('reason', 'unavailable')}. The bootstrap is fixed at "
          f"{fmt(pr['resamples'], 'int')} resamples with seed {fmt(pr['seed'], 'int')}.")
    w("")
    cov = pr.get("coverage")
    if cov:
        band = pr.get("coverage_band") or [None, None]
        null, eff = cov.get("null", {}), cov.get("effect", {})
        status = ("calibrated" if pr.get("coverage_checked") else "**uncalibrated**")
        w(f"Coverage status: {status}. Simulated at the corpus design "
          f"({fmt(null.get('templates'), 'int')} templates, {fmt(null.get('classes'), 'int')} "
          f"classes, {fmt(null.get('sims'), 'int')} simulations of "
          f"{fmt(null.get('resamples'), 'int')} resamples each), the interval covered the "
          f"true delta in {fmt(null.get('coverage'), 'pct')} of corpora under a null delta "
          f"and {fmt(eff.get('coverage'), 'pct')} under a delta of "
          f"{fmt(eff.get('true_delta'), 'p')}; the required band is "
          f"{fmt(band[0], 'pct')}–{fmt(band[1], 'pct')}.")
        if pr.get("available") and null.get("templates") != pr.get("clusters"):
            w("")
            w(f"This run has {fmt(pr['clusters'], 'int')} templates, not the "
              f"{fmt(null.get('templates'), 'int')} the coverage was simulated at, so "
              "the calibration does not transfer to it: treat the interval as "
              "uncalibrated here.")
    else:
        w("Coverage status: **uncalibrated** (no coverage record).")
    w("")

    # ---------------------------------------------------------------- per class
    w("## Recall per class")
    w("")
    w("Caught = BLOCKED with a BLOCKER finding from an expected rule or check; for an "
      "instance whose expected severity is ADVISORY, any finding from an expected rule "
      "or check (DESIGN §5). "
      "The fired columns count instances per rule; `:ADVISORY` marks a non-blocking finding.")
    w("")
    w(f"| class | name | tier | n | shipped `{shipped}` | extended `{extended}` "
      "| expected rule | fired (shipped) | fired (extended) |")
    w("|---|---|---|---|---|---|---|---|---|")
    by_class = numbers["recall"]["by_class"]
    fired = numbers["fired"]["by_class"]
    for c in sorted(by_class, key=_class_key):
        meta = numbers["classes"].get(c, {})
        cells = by_class[c]
        n = (cells.get(shipped) or cells.get(extended) or {}).get("n")
        rules = ", ".join(f"`{r}`" for r in meta.get("rules", [])) or "—"
        w(f"| {c} | {meta.get('name')} | {meta.get('tier')} | {fmt(n, 'int')} "
          f"| {rate_cell(cells.get(shipped))} | {rate_cell(cells.get(extended))} "
          f"| {rules} | {_fired((fired.get(c) or {}).get(shipped))} "
          f"| {_fired((fired.get(c) or {}).get(extended))} |")
    w("")
    ca = numbers["recall"]["class_avg"]
    w(f"Class-averaged recall (unweighted over the classes present): shipped "
      f"{fmt((ca.get(shipped) or {}).get('value'), 'p')}, extended "
      f"{fmt((ca.get(extended) or {}).get('value'), 'p')}.")
    w("")

    w("### Recall per variant")
    w("")
    if "D06" in numbers["recall"]["by_class_variant"]:
        w("D06's variants carry different tiers, so its class rate mixes a deterministic "
          "variant with referent-only ones; the variant rows are the readable unit.")
        w("")
    w(f"| class | variant | variant tier | shipped `{shipped}` | extended `{extended}` |")
    w("|---|---|---|---|---|")
    for c in sorted(numbers["recall"]["by_class_variant"], key=_class_key):
        meta = numbers["classes"].get(c, {})
        for v, cells in sorted(numbers["recall"]["by_class_variant"][c].items()):
            tier = (meta.get("variant_tiers") or {}).get(v, meta.get("tier"))
            w(f"| {c} | {v} | {tier} | {rate_cell(cells.get(shipped))} "
              f"| {rate_cell(cells.get(extended))} |")
    w("")

    # ---------------------------------------------------------------- false blocks
    w("## False blocks on clean controls")
    w("")
    w("| profile | false-block rate | by check | by rule |")
    w("|---|---|---|---|")
    for p in prof["run"]:
        fb = numbers["false_block"][p]
        c_ = {"k": fb["count"], "n": fb["n"], "rate": fb["rate"],
              "wilson_low": fb["wilson_low"], "wilson_high": fb["wilson_high"]}
        w(f"| `{p}` | {rate_cell(c_)} | {_fired(fb['by_check'])} | {_fired(fb['by_code'])} |")
    w("")

    # ---------------------------------------------------------------- secondary
    w("## Secondary outcomes")
    w("")
    w("| profile | recall (all planted) | any-blocker recall | attribution accuracy | advisory-only detections |")
    w("|---|---|---|---|---|")
    for p in prof["run"]:
        w(f"| `{p}` | {rate_cell(numbers['recall']['overall'][p])} "
          f"| {rate_cell(numbers['any_block']['overall'][p])} "
          f"| {rate_cell(numbers['attribution']['overall'][p])} "
          f"| {rate_cell(numbers['advisory_only'][p])} |")
    w("")
    w("Attribution accuracy is computed among planted instances that were blocked for "
      "any rule: the fraction where an expected rule or check fired.")
    w("")

    # ---------------------------------------------------------------- wall time
    w("## Wall time and noise floor")
    w("")
    w("| profile | mean ms per instance | max ms | n |")
    w("|---|---|---|---|")
    for p in prof["run"]:
        wm = numbers["wall_ms"][p]
        w(f"| `{p}` | {fmt(wm['mean'], 'ms')} | {fmt(wm['max'], 'ms')} | {fmt(wm['n'], 'int')} |")
    w("")
    rep = numbers.get("replicate_identical")
    if rep is None:
        w("The replicate run was not made (`--repeat 2` not given), so run-to-run "
          "identity is unmeasured for this record.")
    elif rep:
        w("The layer was run twice on the same bytes and the two row files were "
          "byte-identical apart from wall time: run-to-run spread is zero by "
          "measurement, not quoted as an interval.")
    else:
        w("**The replicate run differed from the first** beyond wall time; see Deviations.")
    w("")

    # ---------------------------------------------------------------- environment
    env = numbers["environment"]
    git = env.get("git") or {}
    w("## Environment")
    w("")
    w("```")
    for key, value in (("python", env.get("python")), ("platform", env.get("platform")),
                       ("git sha", git.get("sha")), ("tree dirty", git.get("dirty")),
                       ("crossaudit", env.get("crossaudit_file")),
                       ("generation seed", f"{env.get('generation_seed')} "
                                           f"(from {env.get('generation_seed_source')})"),
                       ("corpus manifest sha256", env.get("corpus_manifest_sha256")),
                       ("taxonomy sha256", env.get("taxonomy_sha256")),
                       ("checks contracts sha256", env.get("checks_contracts_sha256")),
                       ("rows sha256", env.get("rows_sha256")),
                       ("utc start", env.get("utc_start")), ("utc end", env.get("utc_end"))):
        w(f"{key + ':':<26}{value}")
    w("```")
    w("")

    # ---------------------------------------------------------------- deviations
    w("## Deviations")
    w("")
    devs = []
    for p in prof.get("unknown") or []:
        devs.append(f"Profile `{p}` did not resolve in this tree and was not run; "
                    "every number for it is absent rather than zero.")
    run_errors = numbers["errors"]["run"]
    instance_errors = [e for e in run_errors if e.get("instance_id")]
    if instance_errors:
        devs.append(f"{fmt(len(instance_errors), 'int')} instance-level errors were "
                    "recorded in `run.json` (a check raised, or files differed from the "
                    "manifest); errored rows count as not caught and not blocked.")
    if rep is False:
        devs.append("The replicate run was not byte-identical to the first.")
    if not devs:
        devs.append("None recorded by the runner.")
    for d in devs:
        w(f"- {d}")
    w("")

    # ---------------------------------------------------------------- limitations
    w("## Limitations")
    w("")
    w("Fixed text; the full statement is DESIGN.md §6, which binds this record.")
    w("")
    w("- **Synthetic.** Data follow the governing relation plus Gaussian noise; a "
      "class caught here is caught on a well-formed increment, nothing more.")
    w("- **Single fault.** Each defective instance carries one planted edit; "
      "interactions between defects are unmeasured.")
    w("- **Planted means known.** Ground truth is exact because it was planted; it "
      "says nothing about how often any class occurs in real work.")
    w("- **Deterministic layer only.** The model rung is prepared (`run_auditor.py`) "
      "but not run in this record.")
    w("- **Declarations are honest by construction.** The corpus writes the "
      "declarations a compliant generator would; whether real generators do is a "
      "separate study.")
    w("- **One author, one vendor.** The pack and the corpus were written by the "
      "same agent line; cross-vendor review of the measurement code has not happened.")
    w("")
    return "\n".join(L)


def render_file(run_dir: Path | str) -> str:
    path = Path(run_dir) / "numbers.json"
    raw = path.read_bytes()
    return render(json.loads(raw), hashlib.sha256(raw).hexdigest())


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("run_dir", type=Path)
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)
    text = render_file(args.run_dir)
    if args.out:
        args.out.write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
