"""Audited file_edit — a surgical, fail-closed, recoverable string edit.

The single largest step toward tool-execution parity: instead of rewriting a
whole file, the generator replaces an exact, unique string. The match must be
unique (fail closed on 0 or >1), the write is recovery-pointed, before/after
hashes are the diff the broker records, and — like every write — it never
auto-runs, it waits for a human.
"""
from __future__ import annotations

import pytest

from crossaudit.broker import ToolBroker, write_registry
from crossaudit.broker.recovery import RecoveryStore
from crossaudit.broker.registry import ToolError
from crossaudit.broker.tools_write import MAX_WRITE_BYTES, file_edit
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken


def _writable(paths=("**",)):
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r",
        "tools": ["file_edit", "file_write", "file_read"],
        "paths": list(paths), "writable": True,
        "expires_at": "2100-01-01T00:00:00Z"})


def _seed(cfg, rel, text):
    p = cfg.root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


# -- mechanism --
def test_unique_edit_replaces_and_reports_hashes(cfg):
    p = _seed(cfg, "work/a.py", "hello world\n")
    r = file_edit(cfg, {"path": "work/a.py", "old_string": "world",
                        "new_string": "CrossAudit"}, _writable())
    assert p.read_text() == "hello CrossAudit\n"
    assert r["replacements"] == 1 and r["existed_before"] is True
    assert r["pre_sha256"] and r["post_sha256"] and r["pre_sha256"] != r["post_sha256"]


def test_a_non_unique_match_fails_closed(cfg):
    _seed(cfg, "work/a.py", "x = 1\ny = 2\nx = 1\n")
    with pytest.raises(ToolError) as e:
        file_edit(cfg, {"path": "work/a.py", "old_string": "x = 1",
                        "new_string": "x = 9"}, _writable())
    assert "matches 2" in e.value.reason


def test_replace_all_edits_every_occurrence(cfg):
    p = _seed(cfg, "work/a.py", "x = 1\ny = 2\nx = 1\n")
    r = file_edit(cfg, {"path": "work/a.py", "old_string": "x = 1",
                        "new_string": "x = 9", "replace_all": True}, _writable())
    assert p.read_text() == "x = 9\ny = 2\nx = 9\n" and r["replacements"] == 2


def test_a_string_that_is_not_found_is_refused(cfg):
    _seed(cfg, "work/a.py", "hello\n")
    with pytest.raises(ToolError):
        file_edit(cfg, {"path": "work/a.py", "old_string": "nope",
                        "new_string": "z"}, _writable())


def test_editing_a_missing_file_is_refused(cfg):
    with pytest.raises(ToolError):
        file_edit(cfg, {"path": "work/missing.py", "old_string": "a",
                        "new_string": "b"}, _writable())


def test_identical_old_and_new_is_refused(cfg):
    _seed(cfg, "work/a.py", "a\n")
    with pytest.raises(ToolError):
        file_edit(cfg, {"path": "work/a.py", "old_string": "a",
                        "new_string": "a"}, _writable())


@pytest.mark.parametrize("evil", ["../outside.txt", "/etc/passwd", "~/x"])
def test_edit_refuses_escape(cfg, evil):
    with pytest.raises(ToolError):
        file_edit(cfg, {"path": evil, "old_string": "a", "new_string": "b"},
                  _writable())


def test_edit_refuses_out_of_scope(cfg):
    _seed(cfg, "secret.env", "TOKEN=abc\n")
    with pytest.raises(ToolError):
        file_edit(cfg, {"path": "secret.env", "old_string": "abc",
                        "new_string": "xyz"}, _writable(paths=("work/**",)))


def test_edit_over_the_byte_limit_refused(cfg):
    _seed(cfg, "work/big.py", "seed\n")
    with pytest.raises(ToolError):
        file_edit(cfg, {"path": "work/big.py", "old_string": "seed",
                        "new_string": "x" * (MAX_WRITE_BYTES + 1)}, _writable())


def test_recovery_point_restores_prior_content(cfg):
    p = _seed(cfg, "work/a.py", "original text\n")
    rec = RecoveryStore(cfg)
    record = rec.snapshot("work/a.py")
    file_edit(cfg, {"path": "work/a.py", "old_string": "original",
                    "new_string": "changed"}, _writable())
    assert p.read_text() == "changed text\n"
    rec.restore(record)
    assert p.read_text() == "original text\n"


# -- the broker gate: an edit is audited and never auto-runs --
def test_broker_gates_edit_behind_approval(cfg, tmp_path):
    _seed(cfg, "work/x.py", "keep this\n")
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    r = broker.execute(
        {"tool": "file_edit", "args": {"path": "work/x.py",
         "old_string": "keep", "new_string": "drop"}},
        _writable(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "needs_approval"
    assert (cfg.root / "work/x.py").read_text() == "keep this\n"   # nothing changed
    assert broker.ledger.verify().ok and broker.ledger.verify().count >= 2


def test_broker_denies_edit_under_readonly_grant(cfg, tmp_path):
    _seed(cfg, "work/x.py", "keep\n")
    broker = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))
    readonly = CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["file_edit"],
        "paths": ["**"], "expires_at": "2100-01-01T00:00:00Z"})
    r = broker.execute(
        {"tool": "file_edit", "args": {"path": "work/x.py",
         "old_string": "keep", "new_string": "drop"}},
        readonly, cfg=cfg, run_id="r", now_epoch=0)
    assert r.status == "refused" and "read-only" in r.reason
    assert (cfg.root / "work/x.py").read_text() == "keep\n"
