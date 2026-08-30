"""F1 — the console shows the AUDITED report, and says when the disk disagrees.

**What was wrong, and why no diff showed it.** `verify` used to read the report
from the working tree. That meant a report rewritten after its audit made
verification fail — an accidental detector nobody designed. The verifier merge
correctly changed `verify` to read the commit the receipt cites, which is right,
and which removed the accidental detector. Nothing replaced it, and
`console/streams.py` plus `console/overview.py` read exactly the rewritten file.

Every gate asked "is this change correct?" and none could ask "who holds this
property now?" — here the answer went from "verify, by accident" to "nobody".

**Driven, it was worse than misleading prose.** Editing a completed report on
disk flipped the verdict the console reported from PASS to BLOCKED, moved the
dashboard counters, and injected a fabricated BLOCKER whose hand-typed
observation was attributed to the independent auditor — the one artifact whose
independence is the product's whole claim.

**The guards below are specified with their mutations (D64).** Each mutation is
the exact code that shipped before this fix, and each is asserted to redden with
a message naming what broke, so a future reader knows which property died. A
guard that is not shown red is a claim, not a check.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from crossaudit.config import load
from crossaudit.console import overview, streams

CONFIG = (
    "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
    "auditor: {vendor: openai, provider: openai_compat, model: m,"
    " key_env: CROSSAUDIT_AUDITOR_KEY}\ngenerator: {vendor: anthropic}\n"
    "scope: {dirs: [work]}\nledger: {dir: cycles}\nstate: {dir: .crossaudit}\n"
    "checks: [parseable]\n")

REPORT = """# Audit Report — t/p@{sha}

| | |
|---|---|
| verdict | **{verdict}** |
| round | 1 |
| constitution | `abc123def456` |
| auditor | `openai_compat:gpt` |

## Model findings

{findings}
"""

FABRICATED = ("### [BLOCKER] CA-FAKE-999 — work/a.md\n"
              "This observation was typed by hand after the audit finished.\n")


def _git(*args, cwd: Path) -> str:
    return subprocess.run(["git", *args], cwd=cwd, check=True, text=True,
                          capture_output=True).stdout.strip()


def _build_audited(root: Path):
    """A committed, PASSED cycle carrying a receipt that cites its report
    commit — the shape a real `crossaudit run --write-ledger` leaves behind."""
    root.mkdir(parents=True)
    _git("init", "-q", "-b", "main", cwd=root)
    _git("config", "user.email", "t@local.invalid", cwd=root)
    _git("config", "user.name", "T", cwd=root)
    (root / "AUDIT_RULES.md").write_text("### CA-TXT-001\n**BLOCKER.** exact\n")
    (root / "crossaudit.yml").write_text(CONFIG)
    cfg = load(root / "crossaudit.yml")
    cycle = root / "cycles" / "aaaaaaaaaaaa-r1"
    cycle.mkdir(parents=True)
    report = cycle / "report.md"
    report.write_text(REPORT.format(sha="aaaaaaaaaaaa", verdict="PASS",
                                    findings=""), newline="\n")
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "audit report", cwd=root)
    commit = _git("rev-parse", "HEAD", cwd=root)
    (cycle / "receipt.json").write_text(json.dumps(
        {"ledger": {"report_commit": commit, "cycle_path": "cycles/aaaaaaaaaaaa-r1",
                    "audit_repo": "local", "report_sha256": ""}}))
    _git("add", "-A", cwd=root)
    _git("commit", "-q", "-m", "receipt", cwd=root)
    return cfg, report


@pytest.fixture()
def audited(tmp_path: Path):
    return _build_audited(tmp_path / "proj")


def _rewrite_after_the_audit(report: Path) -> None:
    """The reported symptom, exactly: flip the verdict and add a finding whose
    prose a person typed, after the audit finished."""
    report.write_text(REPORT.format(sha="aaaaaaaaaaaa", verdict="BLOCKED",
                                    findings=FABRICATED), newline="\n")


# ------------------------------------------------------------- the property
def test_a_rewritten_report_does_not_reach_the_screen_as_the_auditors_words(audited):
    cfg, report = audited
    _rewrite_after_the_audit(report)

    stream = [row for row in streams.auditor_stream(cfg, routing=[])
              if row["kind"] == "auditor"]
    assert len(stream) == 1
    row = stream[0]
    assert row["verdict"] == "PASS", (
        "the console reported the edited verdict: a report rewritten after its "
        "audit reached the screen as the auditor's own finding")
    assert row["findings"] == [], (
        "the console reported the edited verdict: hand-typed prose reached the "
        "screen attributed to the independent auditor")
    assert "CA-FAKE-999" not in json.dumps(row)


def test_the_dashboard_counters_do_not_move_when_a_report_is_rewritten(audited):
    cfg, report = audited
    before = [(m["label"], m["value"]) for m in
              overview.metrics(cfg, overview.read_cycles(cfg))]
    _rewrite_after_the_audit(report)
    after = [(m["label"], m["value"]) for m in
             overview.metrics(cfg, overview.read_cycles(cfg))]
    assert before == after, (
        "the console reported the edited verdict: editing a report on disk "
        "moved the supervision dashboard's counters")


def test_the_person_is_told_the_disk_copy_differs_rather_than_silently_corrected(audited):
    """Both halves. Showing the audited bytes without saying so would hide an
    edit the person may have made deliberately; saying so while still rendering
    the edited bytes would still put invented prose under the auditor's name."""
    cfg, report = audited
    clean = [row for row in streams.auditor_stream(cfg, routing=[])
             if row["kind"] == "auditor"][0]
    assert clean["report_state"] == "committed"
    assert clean["report_note"] == ""

    _rewrite_after_the_audit(report)
    row = [row for row in streams.auditor_stream(cfg, routing=[])
           if row["kind"] == "auditor"][0]
    assert row["report_state"] == "drifted", (
        "the divergence is not signalled, so a person whose ledger directory "
        "was edited is never told")
    assert "differs" in row["report_note"]
    # And the sentence names the command that settles it: the receipt is honest
    # in every one of these cases, so the useful thing to hand someone is the
    # way to check it.
    assert "crossaudit verify" in row["report_note"]
    assert overview.read_cycles(cfg)[0].report_state == "drifted"


def test_a_report_that_is_not_committed_says_so_rather_than_passing_as_final(audited):
    """The spec's explicit trap: do not silently fall back to disk under the
    same presentation, which is the defect wearing a fallback."""
    cfg, _ = audited
    cycle = cfg.root / "cycles" / "bbbbbbbbbbbb-r1"
    cycle.mkdir(parents=True)
    (cycle / "report.md").write_text(
        REPORT.format(sha="bbbbbbbbbbbb", verdict="PASS", findings=""),
        newline="\n")
    rows = {row["round"]: row for row in streams.auditor_stream(cfg, routing=[])
            if row["kind"] == "auditor"}
    fresh = [row for row in streams.auditor_stream(cfg, routing=[])
             if row["kind"] == "auditor" and row["report_state"] != "committed"]
    assert len(fresh) == 1
    assert fresh[0]["report_state"] == "uncommitted"
    assert "not committed yet" in fresh[0]["report_note"]


def test_the_receipts_commit_is_preferred_over_whatever_git_last_touched(audited):
    """The push-access case, which needs no local access at all: a collaborator
    commits an edited report and it arrives by `git pull`. `git log -1` would
    hand back the rewrite; the receipt still names the audit. This is why the
    receipt is consulted first and the git derivation is only a fallback."""
    cfg, report = audited
    _rewrite_after_the_audit(report)
    _git("add", "-A", cwd=cfg.root)
    _git("commit", "-q", "-m", "rewrite the report", cwd=cfg.root)

    row = [row for row in streams.auditor_stream(cfg, routing=[])
           if row["kind"] == "auditor"][0]
    assert row["verdict"] == "PASS", (
        "the console reported the edited verdict: a report rewritten AND "
        "committed still reached the screen as the auditor's words")
    assert row["findings"] == []
    # And it is still reported as drifted, which I had expected to be
    # "committed" and was wrong about. The comparison is against the AUDITED
    # bytes, not against whatever HEAD happens to hold, so committing the
    # rewrite does not make it agree — the person is told the file on disk
    # differs from the one that was audited, which in the push-access case is
    # exactly the fact they need.
    assert row["report_state"] == "drifted"
    assert "differs" in row["report_note"]


def test_a_derived_commit_is_never_presented_as_the_audited_one(audited):
    """R2 — F1's own claim, alive in a narrower state.

    `_cited_report_commit` prefers the receipt's `ledger.report_commit`. When
    that is absent — a legacy receipt, a `--no-write-ledger` run — the fallback
    asks git which commit last touched the file. That answer is not the audited
    commit: for a report rewritten AFTER its audit and then committed, it is the
    REWRITE. And the console reported `committed`, so it did not merely omit
    provenance, it ASSERTED it. Omission would have been a gap; assertion is the
    original defect at a smaller size.

    Asserted at the CONSUMER, where a person is misled, not at the holder. The
    auditor's zero-case: the whole property rests on one function and nothing
    downstream would notice if it started returning disk bytes again.
    """
    cfg, report = audited
    # A receipt that cites no commit — the shape legacy and --no-write-ledger
    # runs leave behind.
    receipt = report.parent / "receipt.json"
    receipt.write_text(json.dumps(
        {"ledger": {"report_commit": "", "cycle_path": "cycles/aaaaaaaaaaaa-r1",
                    "audit_repo": "local", "report_sha256": ""}}))
    _rewrite_after_the_audit(report)
    _git("add", "-A", cwd=cfg.root)
    _git("commit", "-q", "-m", "rewrite and commit", cwd=cfg.root)

    row = [row for row in streams.auditor_stream(cfg, routing=[])
           if row["kind"] == "auditor"][0]
    assert row["report_state"] != "committed", (
        "the console asserted that a derived commit is the audited one: a "
        "report rewritten after its audit is presented as audited")
    assert row["report_state"] == "unverified"
    assert "cannot confirm" in row["report_note"]
    assert "crossaudit verify" in row["report_note"]
    # The dashboard must carry the same state, or the two surfaces disagree
    # about the same report.
    assert overview.read_cycles(cfg)[0].report_state == "unverified"


# ------------------------------------------------------------------ mutations
# The shipped code, restored verbatim. Each must turn a named assertion red.
MUTATIONS = (
    ("overview.read_report_sources reads the working tree again — the code that "
     "shipped before this fix",
     "overview", """        text = (committed if committed is not None else disk)""",
     """        text = disk"""),
    ("the divergence signal is dropped, so the audited bytes are shown and the "
     "person is never told their copy differs",
     "overview", """        if self.state == "drifted":""",
     """        if False:"""),
    ("the receipt's cited commit is ignored in favour of whatever git last "
     "touched, which is the rewrite itself",
     "overview", """            commit = _cited_report_commit(report.parent)""",
     """            commit = \"\""""),
    ("the fallback goes back to ASSERTING that a derived commit is the audited "
     "one — F1's own claim alive in a narrower state",
     "overview", """        if not self.cited:""", """        if False:"""),
)


@pytest.mark.parametrize("why,module,before,after", MUTATIONS,
                         ids=[m[0][:38] for m in MUTATIONS])
def test_the_guard_is_shown_to_fail(why, module, before, after, audited, monkeypatch,
                                    tmp_path):
    """Break the product on purpose and watch a named assertion catch it.

    The mutant is compiled from the real source and swapped in, so this is the
    shipping code being broken rather than a caricature of it. The FIRST error
    line is read, not merely the exit status: three times a guard of mine went
    red for an unrelated reason and I recorded it as a catch.
    """
    import crossaudit.console.overview as overview_module

    source = Path(overview_module.__file__).read_text()
    assert source.count(before) == 1, (
        f"the mutation for {why!r} no longer applies; the source moved and this "
        f"guard is no longer known to catch it")
    mutated = source.replace(before, after)
    namespace: dict = {"__name__": "crossaudit.console.overview",
                       "__file__": overview_module.__file__}
    exec(compile(mutated, overview_module.__file__, "exec"), namespace)
    for name in ("read_report_sources", "read_cycles", "metrics", "ReportSource"):
        monkeypatch.setattr(overview_module, name, namespace[name])
    monkeypatch.setattr(streams, "read_report_sources",
                        namespace["read_report_sources"])

    # A FRESH project per check. Sharing one would let an earlier check's
    # rewrite make a later one red, and a mutation caught by the previous
    # test's side effect has not been shown to be caught at all — the exact
    # "red for the wrong reason" this discipline exists to prevent.
    caught = []
    for index, (name, check) in enumerate((
            ("auditor words", test_a_rewritten_report_does_not_reach_the_screen_as_the_auditors_words),
            ("dashboard counters", test_the_dashboard_counters_do_not_move_when_a_report_is_rewritten),
            ("the person is told", test_the_person_is_told_the_disk_copy_differs_rather_than_silently_corrected),
            ("receipt over git log", test_the_receipts_commit_is_preferred_over_whatever_git_last_touched),
            ("derived is not asserted", test_a_derived_commit_is_never_presented_as_the_audited_one))):
        try:
            check(_build_audited(tmp_path / f"mutant-{index}"))
        except AssertionError as exc:
            caught.append((name, str(exc).split("\n")[0][:120]))
    assert caught, f"MUTATION SURVIVED — {why}. No guard went red."


# ------------------------------------------------------- what a person reads
def test_the_console_renders_the_note_where_the_person_reads_the_verdict():
    """The payload carrying a sentence is not the same as a person seeing it.

    The auditor row is deliberately excluded from the conversation transcript,
    so it reaches people through two surfaces: the review card (the primary one)
    and the Audits view. Both render it, and neither renders it inside the
    findings list — inside, it would read as something the auditor observed,
    which is the exact confusion this fix exists to end.

    Driven in a real browser at 1440 and 390, light and dark, both locales:
    `_ui_findings/f1-report-source/evidence/render.json`.
    """
    from crossaudit.console.page import PAGE

    assert "report-provenance" in PAGE
    # The Audits view, through the auditor turn.
    turn = PAGE[PAGE.index("if(m.kind === 'auditor'){"):]
    turn = turn[:turn.index("if(m.kind === 'context_condensed')")]
    assert "m.report_note" in turn
    assert turn.index("report-provenance") > turn.index('class="finding"'), (
        "the note is rendered inside the findings, where it reads as something "
        "the auditor observed")
    # The review card, which is where a person meets the result first.
    card = PAGE[PAGE.index("const roundLines="):]
    card = card[:card.index("function runCard(d)")]
    assert "report_note" in card and "report-provenance" in card
    # Both sentences are translated: neither is composed, so both are fixed
    # entries rather than patterns.
    for english, chinese in (
            ("The copy of this report on disk differs from the audited one "
             "shown here. Run crossaudit verify to check the record.",
             "磁盘上的这份报告与此处显示的已审计版本不同。请运行 crossaudit verify 核对记录。"),
            ("This report is not committed yet, so it cannot be verified yet.",
             "这份报告尚未提交，因此暂时无法核验。")):
        assert f'"{english}":"{chinese}"' in PAGE


def test_the_review_card_survives_a_run_that_is_not_superseding_it():
    """R3 — the F1/F7 interaction, driven instead of argued about.

    I reported this interaction as "named" and marked the combined screen
    "reasoned about, not observed". The cross-vendor audit built the state and
    it failed: with a completed cycle AND an active stream, Chromium showed the
    live draft and no review card, so the provenance line went with it.

    The cause predates both fixes — the card was suppressed for the duration of
    ANY run, because the run card takes the stage. F1 attached the provenance to
    that card and inherited the suppression, and F7 made the state reachable
    enough to see. The property held except while streaming, which is except
    when the surface is busiest and a person most needs to know what was
    reviewed.

    NARROWED rather than removed, and both edges are pinned here because a
    one-sided guard would be satisfied by deleting the line: a run CONTINUING
    this cycle is producing a verdict that supersedes the card, and must still
    hide it; a run on anything else must not.

    Driven, both edges and both mutations, in `_ui_findings/f1f7-coexist/`.
    """
    from crossaudit.console.page import PAGE

    card = PAGE[PAGE.index("function reviewCard(d){"):]
    card = card[:card.index("\nfunction ")]
    assert "String(p.continuation_cycle||'')===String(cycle.id||'')" in card, (
        "the review card is suppressed for the whole of any run again, so the "
        "report's provenance disappears exactly while a draft is streaming")
    # ...and it is still suppressed for the case that would state a superseded
    # outcome. Removing the guard entirely is the other way to get this wrong.
    assert "if(p&&!p.finished&&" in card
    assert "if(p&&!p.finished)return '';" not in card
