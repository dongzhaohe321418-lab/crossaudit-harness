"""Enterprise invariant: a secret never enters a prompt, a log, the evidence
ledger, or a receipt.

This file adversarially plants realistic credentials (an AWS access-key id, a
GitHub token, an OpenSSH private-key block, a hard-coded ``api_key =`` value) and
drives the REAL governed paths, asserting at each seam that only hashes/metadata
and KIND labels ever surface — never the credential value:

  (a) file_read of a committed secret file -> the Evidence Ledger records only
      tool/status/hash fields; the raw secret is NOT anywhere in the ledger
      bytes, nor in the Auditor's allowlisted evidence_view.
  (b) a git_commit that would write a secret is refused by secretscan; the
      ToolError message names only the KIND, never the value, and even a FAILED
      brokered execution leaks nothing into the ledger, and HEAD does not move.
  (c) secretscan.scan_text / first_finding return only KIND labels.
  (d) the generator's built-in tool catalog (routing.build_catalog) is pure
      static tool metadata — no secret material even with secrets in env/tree.
  (e) a receipt's tool_evidence block binds ONLY the ledger head + entry count;
      it cannot surface a payload, even a hypothetical secret-bearing one.

Every test performs the attack and asserts the defense holds — remove the
defense and the assertion fails.
"""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from crossaudit import gitio
from crossaudit.broker import (
    ToolBroker,
    default_registry,
    write_registry,
)
from crossaudit.broker import secretscan
from crossaudit.broker.registry import ToolError
from crossaudit.broker.routing import (
    broker_for,
    build_catalog,
    evidence_path,
    evidence_view,
    readonly_catalog,
    write_catalog,
)
from crossaudit.broker.tools_git import git_commit
from crossaudit.ledger import EvidenceLedger
from crossaudit.policy import CapabilityToken
from crossaudit.receipt.build import _tool_evidence

# -- a handful of realistic, high-signal secrets ---------------------------------
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"                              # AKIA + 16 chars
GH_TOKEN = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"   # ghp_ + 36 chars
_KEY_BODY = ("b3BlbnNzaC1rZXktdjEAAAAABG5vbmUAAAAEbm9uZQAAAAAAAAAB"
             "AAAAMwAAAAtzc2gtZWQyNTUxOTAAAABDEADBEEFcafef00dBaZ9")
PRIVATE_KEY = (f"-----BEGIN OPENSSH PRIVATE KEY-----\n{_KEY_BODY}\n"
               "-----END OPENSSH PRIVATE KEY-----\n")
_HARDCODED_VALUE = "ab12cd34ef56gh78ij90"
HARDCODED = f'api_key = "{_HARDCODED_VALUE}"'

#: The raw credential values that must never appear in any log/ledger/receipt.
SECRET_VALUES = (AWS_KEY, GH_TOKEN, _KEY_BODY, _HARDCODED_VALUE)

#: One file that carries every planted secret.
SECRETS_BLOB = (
    f"aws_access_key_id = {AWS_KEY}\n"
    f"github_token = {GH_TOKEN}\n"
    f"{PRIVATE_KEY}"
    f"{HARDCODED}\n"
)


def _token(paths=("**",), tools=("file_read", "search", "git_status", "doctor"),
           **kw):
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": list(tools),
        "paths": list(paths), "expires_at": "2100-01-01T00:00:00Z", **kw})


def _commit_file(cfg, rel: str, content: str) -> None:
    """Commit ``content`` at ``rel`` so file_read (committed-tree reader) sees it."""
    target = cfg.root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    gitio.git("add", rel, cwd=cfg.root)
    gitio.git("-c", "user.name=t", "-c", "user.email=t@t",
              "commit", "-m", f"add {rel}", cwd=cfg.root)


def _assert_no_secret(blob: bytes | str) -> None:
    data = blob if isinstance(blob, bytes) else blob.encode("utf-8")
    for value in SECRET_VALUES:
        assert value.encode("utf-8") not in data, f"leaked secret value {value!r}"


# -- (a) file_read: the ledger records hashes/metadata, never the raw content ----
def test_file_read_of_secret_never_writes_content_to_ledger(cfg, tmp_path):
    _commit_file(cfg, "secrets.txt", SECRETS_BLOB)
    b = ToolBroker(default_registry(), EvidenceLedger(tmp_path / "ev.jsonl"))

    r = b.execute({"tool": "file_read", "args": {"path": "secrets.txt"}},
                  _token(), cfg=cfg, run_id="r", now_epoch=0)

    # The read genuinely happened — the secret really is in the returned output,
    # so any leak into the ledger would be a real one, not a no-op.
    assert r.ok
    assert AWS_KEY in r.output["content"] and _KEY_BODY in r.output["content"]

    # The whole ledger file — every recorded byte — carries no secret value.
    _assert_no_secret(b.ledger.path.read_bytes())
    # And no individual payload does either (belt-and-suspenders).
    for entry in b.ledger.entries():
        _assert_no_secret(json.dumps(entry))
        payload = entry.get("payload", {})
        assert "content" not in payload            # the raw text never enters
    # The chain is intact: call + decision + result, and it re-derives.
    rep = b.ledger.verify()
    assert rep.ok and rep.count == 3


def test_auditor_evidence_view_of_secret_read_exposes_no_content(cfg):
    _commit_file(cfg, "secrets.txt", SECRETS_BLOB)
    b = broker_for(cfg)                             # ledger at the project path

    r = b.execute({"tool": "file_read", "args": {"path": "secrets.txt"}},
                  _token(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.ok and AWS_KEY in r.output["content"]

    rows = evidence_view(cfg)                       # what the Auditor may see
    assert rows                                     # a read was recorded
    _assert_no_secret(json.dumps(rows))
    for row in rows:
        assert "content" not in row
    # The on-disk project ledger the view reads from is itself clean.
    _assert_no_secret(evidence_path(cfg).read_bytes())


# -- (b) git_commit: refuse the secret; leak neither its value nor the tree ------
def test_git_commit_refuses_secret_without_echoing_the_value(cfg):
    before = gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip()
    (cfg.root / "leak.txt").write_text(f"deploy key\n{PRIVATE_KEY}")

    with pytest.raises(ToolError) as exc:
        git_commit(cfg, {"message": "add deploy key"},
                   _token(tools=("git_commit",), writable=True))

    msg = str(exc.value)
    assert "refused" in msg and "private key" in msg      # names the KIND
    _assert_no_secret(msg)                                 # never the value
    # The commit did not happen and staging was reset — no half-committed leak.
    assert gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip() == before
    staged = gitio.git("diff", "--cached", "--name-only", cwd=cfg.root, check=False)
    assert staged.strip() == ""


def test_brokered_failed_commit_leaks_no_secret_into_ledger(cfg, tmp_path):
    # Even when a human approves the commit, the secret-scan gate fails it; the
    # broker records a FAILED tool_result — and that record must not carry the
    # secret. We grant approval so the handler actually runs and raises.
    before = gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip()
    (cfg.root / "leak.txt").write_text(f"deploy key\n{PRIVATE_KEY}")
    grant_all = lambda proposal, decision, cfg_, run_id: SimpleNamespace(
        granted=True, reason="approved-for-test")
    b = ToolBroker(write_registry(), EvidenceLedger(tmp_path / "ev.jsonl"),
                   approver=grant_all)

    r = b.execute({"tool": "git_commit", "args": {"message": "add deploy key"}},
                  _token(tools=("git_commit",), writable=True),
                  cfg=cfg, run_id="r", now_epoch=0)

    assert r.status == "failed"
    assert "refused" in r.reason and "private key" in r.reason
    _assert_no_secret(r.reason)
    # HEAD unmoved (the commit was refused, not merely unrecorded).
    assert gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip() == before
    # call + decision + approval + tool_result, chain intact, and no secret byte.
    rep = b.ledger.verify()
    assert rep.ok and rep.count == 4
    _assert_no_secret(b.ledger.path.read_bytes())


# -- (c) secretscan surfaces KIND labels only, never the value -------------------
@pytest.mark.parametrize("text,value", [
    (f"key={AWS_KEY}", AWS_KEY),
    (f"token={GH_TOKEN}", GH_TOKEN),
    (PRIVATE_KEY, _KEY_BODY),
    (HARDCODED, _HARDCODED_VALUE),
])
def test_scan_text_and_first_finding_return_labels_only(text, value):
    hits = secretscan.scan_text(text)
    assert hits, f"scanner missed a real secret in {text!r}"
    for label in hits:
        assert value not in label                 # a label is a KIND, not a value
        _assert_no_secret(label)
    finding = secretscan.first_finding(text)
    assert finding and value not in finding
    _assert_no_secret(finding)


def test_first_finding_is_empty_on_clean_text():
    assert secretscan.first_finding("a perfectly ordinary sentence") == ""
    assert secretscan.scan_text("a perfectly ordinary sentence") == []


# -- (d) the generator's tool catalog carries no secret material -----------------
def test_build_catalog_contains_no_secret_material(cfg, monkeypatch):
    # Plant secrets both in the environment and in the committed tree; the tool
    # catalog is derived from static tool metadata, so none may appear in it.
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", AWS_KEY)
    monkeypatch.setenv("SOME_PROVIDER_TOKEN", GH_TOKEN)
    _commit_file(cfg, "secrets.txt", SECRETS_BLOB)

    for catalog in (build_catalog(cfg), readonly_catalog(), write_catalog()):
        _assert_no_secret(json.dumps(catalog))

    # Sanity: the catalog is non-trivial, so the "no secret" check is meaningful.
    names = {t["name"] for t in build_catalog(cfg)}
    assert "file_read" in names


# -- (e) a receipt binds only the ledger head + count, never a payload -----------
def test_tool_evidence_binds_only_head_and_count(cfg):
    _commit_file(cfg, "secrets.txt", SECRETS_BLOB)
    b = broker_for(cfg)
    r = b.execute({"tool": "file_read", "args": {"path": "secrets.txt"}},
                  _token(), cfg=cfg, run_id="r", now_epoch=0)
    assert r.ok

    te = _tool_evidence(cfg).block
    assert te is not None
    assert set(te) == {"ledger_head", "entries"}      # nothing else is bound
    assert len(te["ledger_head"]) == 64 and te["entries"] >= 1
    _assert_no_secret(json.dumps(te))


def test_receipt_binding_cannot_surface_a_ledger_payload(cfg):
    # Isolate the receipt layer: whatever a ledger entry's payload holds, the
    # tool_evidence block exposes only head+count. Inject a (hypothetical)
    # secret-bearing payload and confirm the binding cannot leak it.
    led = EvidenceLedger(evidence_path(cfg))
    led.append("tool_call", run_id="r", payload={"tool": "file_read"}, ts="t0")
    led.append("tool_result", run_id="r",
               payload={"smuggled": AWS_KEY, "also": GH_TOKEN}, ts="t1")

    te = _tool_evidence(cfg).block
    assert te is not None and set(te) == {"ledger_head", "entries"}
    assert te["entries"] == 2
    _assert_no_secret(json.dumps(te))                 # the receipt stays clean
