"""The constitution is shown and chosen before it is committed (Ledger D6 #4, D8).

The walkthrough typed a plain-prose task and received `# Constitution —
<PROJECT>` with the placeholder unreplaced and 7 BLOCKERs about `metadata.yml`,
`results.json`, quantities and convergence — while the screen one step earlier
promised the rules would be "drafted from this, shown to you, and committed only
if you agree". It was not drafted, not shown, and committed anyway, and the first
real build was then blocked for lacking a file a prose review would never
contain.

Three separate defects wearing one bug number, and they are fixed separately:

* **not shown** — the show-and-agree step existed but ran only on the drafted
  path; the fallback wrote and committed silently. It now runs on every path.
* **wrong shape** — the CLI wrote the laboratory contract and the science check
  pack for any project. `app.py` and `console/projects.py` already chose per
  project type; the CLI was the outlier.
* **`<PROJECT>`** — substituted only by `draft.render()`, never on the template
  path.

Every test executes the real `init` and reads what it printed and wrote
(AGENTS.md §3.5). The last one mutates the product on purpose and demonstrates
the guard fails (Ledger D10).
"""
from __future__ import annotations

import argparse
import re

import pytest

from crossaudit.cli import main, wizard
from crossaudit.cli.i18n import t


def _args(project, **over) -> argparse.Namespace:
    base = dict(path=str(project), github=False, force=True, no_console=True,
                json=False, auditor_vendor="anthropic",
                auditor_model="claude-opus-4", generator_vendor="openai",
                generator_model="gpt-5", profile=None)
    base.update(over)
    return argparse.Namespace(**base)


def _flat(text: str) -> str:
    """Collapse whitespace before matching.

    `tui.note` wraps, so a sentence the person plainly reads is split across
    lines and indented in the raw stream. Asserting on the raw text would miss
    it — the same shape as the phrase-split-across-an-<em> evasion that defeated
    an earlier guard. Match what is read, not how it was laid out.
    """
    return re.sub(r"\s+", " ", text)


def _init(tmp_path, monkeypatch, capsys, name="proj", describe="", **over):
    project = tmp_path / name
    project.mkdir()
    monkeypatch.setenv("HOME", str(tmp_path / f"home-{name}"))
    # `keys_file()` resolves DEFAULT_KEYS_FILE, which was computed from the real
    # home at import, so setting HOME does not move it. Point it at the sandbox
    # explicitly: without this a developer who happens to have a credentials
    # file gets a different refusal here than CI does, and the test below is
    # about exactly which refusal is printed.
    monkeypatch.setenv("CROSSAUDIT_KEYS_FILE", str(tmp_path / f"keys-{name}.env"))
    for env in ("CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"):
        monkeypatch.delenv(env, raising=False)
    if describe:
        # Non-interactively `tui.text` returns its default, and the default for
        # the description is empty — so `_distil` is never called and the
        # keyless draft failure never happens. Typing something is what reaches
        # it, so the test types something.
        spoken = wizard.tui.text

        def typed(prompt, default="", **kw):
            if "your project" in prompt:
                return describe
            return spoken(prompt, default, **kw)

        monkeypatch.setattr(wizard.tui, "text", typed)
    monkeypatch.chdir(project)
    main.cmd_init(_args(project, **over))
    return project, capsys.readouterr().out


#: A sentence long enough to be a real description, so `_distil` is attempted.
_DESCRIPTION = ("a review of the PV industry; every figure must trace to a "
                "source")


# --------------------------------------------------------------- shown, then written
def test_the_rules_are_shown_and_chosen_before_anything_is_committed(
        tmp_path, monkeypatch, capsys):
    project, out = _init(tmp_path, monkeypatch, capsys)

    # What will be required of their work, in plain language, before the choice.
    flat = _flat(out)
    assert "Before CrossAudit accepts any work, it will check that:" in flat
    assert "it does what you asked for" in flat
    # A choice among named alternatives, not a bare agreement.
    assert "These rules:" in flat
    assert "Use these rules" in flat
    # Shown BEFORE the file is reported written — the ordering is the fix.
    assert flat.index("Before CrossAudit accepts any work") < flat.index(
        "written and committed")
    # The sentence that makes free editing safe to offer.
    assert "Changing the rules never changes a decision already made" in flat


def test_the_promise_does_not_say_drafted_when_no_draft_happened(
        tmp_path, monkeypatch, capsys):
    """Keyless: `_distil` cannot run, so nothing was drafted from anything."""
    _project, out = _init(tmp_path, monkeypatch, capsys, name="nodraft")

    shown = _flat(out[out.index("[4/4]"):])
    assert "A starting point — not drafted from your description" in shown
    # The word may appear only in the failure notice explaining what could not
    # happen, never as a claim that it did.
    for line in shown.splitlines():
        if "drafted" in line and "not drafted" not in line:
            assert "could not draft" in line, f"claims a draft that did not happen: {line}"


def test_amend_is_not_offered_in_the_state_where_it_cannot_run(
        tmp_path, monkeypatch, capsys):
    """`crossaudit amend` is provider-backed; the keyless path must not route to it."""
    _project, out = _init(tmp_path, monkeypatch, capsys, name="noamend")
    shown = _flat(out[out.index("[4/4]"):])
    assert "crossaudit amend" not in shown


# ------------------------------------ the remedy has to work from where you are
def test_setup_never_sends_you_to_the_command_you_are_already_running(
        tmp_path, monkeypatch, capsys):
    """The keyless draft failure printed the provider's own remedy verbatim.

    That remedy is `crossaudit init`, which is correct from a shell and useless
    here: the person is inside `crossaudit init`, and step 3 offered them the
    key one screen ago. Executed, because the defect is in what a real run of a
    real command prints (AGENTS.md §3.5).
    """
    _project, out = _init(tmp_path, monkeypatch, capsys, name="remedy",
                          describe=_DESCRIPTION)
    flat = _flat(out)
    # The failure is reported at all — otherwise the rest asserts over silence.
    assert "could not draft rules from your description" in flat

    # No line sends them to bare `crossaudit init`. `--force` is a different
    # command: it is the one that re-runs setup and stores a key.
    stray = re.findall(r"`crossaudit init`", flat)
    assert not stray, f"setup told the person to run the command they are in: {flat}"

    # And what it says instead is reachable from here, both ways.
    assert "export $CROSSAUDIT_AUDITOR_KEY" in flat
    assert "crossaudit init --force" in flat


def test_a_refusal_this_screen_does_not_understand_is_passed_through(
        tmp_path, monkeypatch, capsys):
    """Only the missing-key remedy is replaced; nothing else is rewritten.

    The rewrite keys on what the refusal CARRIES, so a refusal that carries
    something else must arrive intact. Otherwise a future provider error would
    be quietly reworded into a sentence about API keys.
    """
    from crossaudit.errors import ConfigDenial as _Denial

    def unrelated(*_a, **_k):
        raise _Denial("the model returned nothing this run", env="X_KEY",
                      keys_file="/somewhere/keys.env")

    monkeypatch.setattr(wizard, "_distil", unrelated)
    _project, out = _init(tmp_path, monkeypatch, capsys, name="passthrough",
                          describe=_DESCRIPTION)
    assert "the model returned nothing this run" in _flat(out)


# ------------------------------- the fact you need comes before the decision
def test_the_sentence_that_makes_editing_safe_is_read_before_the_choice(
        tmp_path, monkeypatch, capsys):
    """D8's sentence is what makes editing safe to OFFER, so it precedes the offer.

    Printed after the choice it is a reassurance about a decision already taken;
    printed before, it is the fact the person needs in order to take it.
    """
    _project, out = _init(tmp_path, monkeypatch, capsys, name="ordering")
    flat = _flat(out)
    assert flat.index("Changing the rules never changes a decision already made") \
        < flat.index("These rules:")


def test_the_remedy_guard_fails_when_the_provider_wording_comes_back(
        tmp_path, monkeypatch, capsys):
    """Mutate the real product, run the real guard, watch it catch it (D10).

    Mutation: `_reason_inside_setup` becomes the identity — which is precisely
    what shipped, `tui.warn(... exc.reason)`. Compared against a live unmutated
    run rather than a recorded snapshot.
    """
    _project, honest = _init(tmp_path, monkeypatch, capsys, name="remedybase",
                             describe=_DESCRIPTION)
    assert not re.findall(r"`crossaudit init`", _flat(honest))

    monkeypatch.setattr(wizard, "_reason_inside_setup", lambda exc: exc.reason)
    _project2, mutated = _init(tmp_path, monkeypatch, capsys, name="remedybad",
                               describe=_DESCRIPTION)
    assert re.findall(r"`crossaudit init`", _flat(mutated)), (
        "the mutation did not take; this demonstration proves nothing")


def test_the_ordering_guard_fails_when_the_sentence_moves_back(
        tmp_path, monkeypatch, capsys):
    """Mutation: hold the sentence back until after the choice, as it was.

    The real stream is mutated rather than a copy of the wizard re-implemented,
    so what the guard runs against is the real product printing in the old
    order.
    """
    real_note, real_ok = wizard.tui.note, wizard.tui.ok
    held: list[str] = []

    def hold(text: str) -> None:
        if "Changing the rules never" in text:
            held.append(text)
            return
        real_note(text)

    def release(text: str) -> None:
        while held:
            real_note(held.pop())
        real_ok(text)

    monkeypatch.setattr(wizard.tui, "note", hold)
    monkeypatch.setattr(wizard.tui, "ok", release)
    _project, mutated = _init(tmp_path, monkeypatch, capsys, name="orderbad")
    flat = _flat(mutated)
    assert flat.index("Changing the rules never changes a decision already made") \
        > flat.index("These rules:"), (
            "the mutation did not take; this demonstration proves nothing")


# ------------------------- a frame must not promise a check it does not make
def test_the_frame_never_promises_a_check_over_a_list_of_what_is_not_checked(
        tmp_path, monkeypatch, capsys):
    """"It will check that nothing will be gated" is not a check (§1.5).

    The empty starting point gates nothing, so the sentence its consequences are
    read under says that, rather than promising checking over a list describing
    the absence of it.
    """
    _project, out = _init(tmp_path, monkeypatch, capsys, name="ownframe",
                          profile="own")
    flat = _flat(out)
    assert "There are no rules to check yet, so until you write one:" in flat
    assert "nothing will be blocked, whatever the work says" in flat
    assert t(wizard.GATING_FRAME_KEY) not in flat, (
        "the empty standard checks nothing; it must not say it will")

    # The gating frame is not merely deleted — it is still used where it is true.
    _project2, gated = _init(tmp_path, monkeypatch, capsys, name="generalframe")
    assert t(wizard.GATING_FRAME_KEY) in _flat(gated)


def test_the_frame_guard_fails_when_the_gating_promise_comes_back(
        tmp_path, monkeypatch, capsys):
    """Mutate the real table, run the real guard, watch it catch it (D10)."""
    _project, honest = _init(tmp_path, monkeypatch, capsys, name="framebase",
                             profile="own")
    assert t(wizard.GATING_FRAME_KEY) not in _flat(honest)

    monkeypatch.setitem(wizard.STARTING_POINTS["own"], "frame",
                        wizard.GATING_FRAME_KEY)
    _project2, mutated = _init(tmp_path, monkeypatch, capsys, name="framebad",
                               profile="own")
    assert t(wizard.GATING_FRAME_KEY) in _flat(mutated), (
        "the mutation did not take; this demonstration proves nothing")


# ------------------------------------------------------------- the right shape
def test_a_prose_project_is_not_given_the_laboratory_contract(
        tmp_path, monkeypatch, capsys):
    project, _out = _init(tmp_path, monkeypatch, capsys, name="prose")

    rules = (project / "AUDIT_RULES.md").read_text(encoding="utf-8")
    config = (project / "crossaudit.yml").read_text(encoding="utf-8")
    # The exact artifacts the walkthrough was blocked for.
    for artefact in ("metadata.yml", "results.json", "convergence", "quantities"):
        assert artefact not in rules, f"a prose review must not be gated on {artefact}"
    assert "checks: [parseable, declared, internal, complete]" in config
    assert "schema" not in config.split("checks:")[1].splitlines()[0]


def test_no_placeholder_token_survives_into_a_committed_file(
        tmp_path, monkeypatch, capsys):
    project, _out = _init(tmp_path, monkeypatch, capsys, name="named")
    text = (project / "AUDIT_RULES.md").read_text(encoding="utf-8")
    assert "<PROJECT>" not in text
    assert text.splitlines()[0] == "# Constitution — named"


@pytest.mark.parametrize("profile,expected_checks,marker", [
    ("science", "schema, units, convergence, provenance", "metadata.yml"),
    ("general", "parseable, declared, internal, complete", "TODO"),
])
def test_an_explicit_profile_is_honoured(tmp_path, monkeypatch, capsys,
                                         profile, expected_checks, marker):
    """Science users keep their path; silence never selects it for them."""
    project, _out = _init(tmp_path, monkeypatch, capsys, name=profile,
                          profile=profile)
    assert f"checks: [{expected_checks}]" in (
        project / "crossaudit.yml").read_text(encoding="utf-8")
    assert marker in (project / "AUDIT_RULES.md").read_text(encoding="utf-8")


def test_only_what_i_write_myself_is_offered_and_is_not_a_defect(
        tmp_path, monkeypatch, capsys):
    """An empty standard is a legitimate choice (D8), so doctor must not fail it."""
    project, _out = _init(tmp_path, monkeypatch, capsys, name="own", profile="own")
    rules = (project / "AUDIT_RULES.md").read_text(encoding="utf-8")
    assert "No rules yet." in rules
    assert not [ln for ln in rules.splitlines() if ln.startswith("### CA-")], (
        "the empty starting point must contain no rule headings; naming the "
        "heading FORMAT in the instructions is not a rule")
    # And the claim it makes about itself is true: checks are configured
    # separately from the constitution, so they still run.
    assert "checks: [" in (project / "crossaudit.yml").read_text(encoding="utf-8")

    from crossaudit.config import load as load_cfg
    monkeypatch.setattr(main._selfid, "identity", lambda: {
        "install_mode": "wheel", "code_digest_sha256": "a" * 64,
        "project": "crossaudit", "version": "4.0.0", "lock_digest_sha256": None})
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "a")
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_KEY", "g")
    load_cfg(project / "crossaudit.yml")
    # Per-line classification lives in the full view now (SPEC 6 §4).
    main.cmd_doctor(argparse.Namespace(fix=False, online=False, json=False,
                                       all=True))
    doctor_out = capsys.readouterr().out
    assert "[FAIL] constitution rules" not in doctor_out
    assert "[INFO] constitution rules" in doctor_out
    assert "nothing is gated until you add one" in doctor_out


# ------------------------------------------------- D10: demonstrate it fails
def test_the_guard_fails_if_the_moment_stops_running(tmp_path, monkeypatch, capsys):
    """Mutate the real product, run the real guard, watch it catch it.

    Mutation: `_show_and_agree` returns the template without showing anything —
    the exact behaviour that shipped, where the constitution was written and
    committed silently. Compared against a live run of the unmutated code rather
    than a recorded snapshot, so a collector that quietly stopped looking cannot
    pass this vacuously.
    """
    _project, honest = _init(tmp_path, monkeypatch, capsys, name="baseline")
    assert "Before CrossAudit accepts any work" in honest

    real = wizard._show_and_agree

    def silent(*, target, const_path, const_name, drafted, chosen, description):
        from crossaudit.scaffold import read
        return wizard._substitute_project(read("AUDIT_RULES.md"), target.name), chosen

    monkeypatch.setattr(wizard, "_show_and_agree", silent)
    _project2, mutated = _init(tmp_path, monkeypatch, capsys, name="mutated")
    monkeypatch.setattr(wizard, "_show_and_agree", real)

    assert "Before CrossAudit accepts any work" not in _flat(mutated), (
        "the mutation did not take; this demonstration proves nothing")
    # The assertions the other tests make would fail against this mutation,
    # which is what makes them guards rather than descriptions.
    assert "Changing the rules never changes a decision" not in _flat(mutated)
