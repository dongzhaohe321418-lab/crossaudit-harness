"""P9 — the secret-scan gate: a governed commit never writes a credential to git.

The scanner is conservative (low false positives) and reports only the KIND of
secret, never the value — so a refusal reason never leaks the credential. The
gate refuses even an approved commit (defense-in-depth), and a workspace write
flags credential-shaped content for the Auditor without blocking a recoverable
edit.
"""
from __future__ import annotations

import pytest

from crossaudit import gitio
from crossaudit.broker import secretscan
from crossaudit.broker.registry import ToolError
from crossaudit.broker.tools_git import git_commit
from crossaudit.broker.tools_write import file_write
from crossaudit.policy import CapabilityToken

PRIVATE_KEY = "-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaAAAA...\n"
AWS_KEY = "AKIAIOSFODNN7EXAMPLE"          # AKIA + 16 chars — the AWS id shape
GH_TOKEN = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"   # ghp_ + 36
HARDCODED = 'api_key = "ab12cd34ef56gh78ij90"'


def _tok():
    return CapabilityToken.parse({
        "project_id": "p", "run_id": "r", "tools": ["git_commit", "file_write"],
        "paths": ["**"], "writable": True, "expires_at": "2100-01-01T00:00:00Z"})


# -- the scanner: catches real shapes, ignores placeholders, labels only --
@pytest.mark.parametrize("text,kind", [
    (PRIVATE_KEY, "private key"),
    (f"key={AWS_KEY}", "AWS"),
    (f"token={GH_TOKEN}", "GitHub"),
    ("t = xoxb-123456789012-abcdefghijkl", "Slack"),
    (HARDCODED, "credential"),
])
def test_scan_detects_known_secret_shapes(text, kind):
    hits = secretscan.scan_text(text)
    assert hits and any(kind in h for h in hits)
    # The label never contains the secret value itself.
    for h in hits:
        assert AWS_KEY not in h and GH_TOKEN not in h


@pytest.mark.parametrize("text", [
    'api_key = "your_api_key_placeholder_here"',
    'secret = "changeme_changeme_changeme"',
    'token = "${MY_TOKEN_FROM_ENV_VARIABLE}"',
    'password = "aaaaaaaaaaaaaaaaaaaaaaaa"',      # single repeated char
    "just a normal sentence with no secrets at all",
])
def test_scan_ignores_placeholders_and_prose(text):
    assert secretscan.scan_text(text) == []


def test_scan_paths_flags_a_dotenv_but_not_a_template():
    assert secretscan.scan_paths(["config/.env"])
    assert secretscan.scan_paths([".env.example"]) == []
    assert secretscan.scan_paths(["src/app.py"]) == []


# -- the commit gate: refuses a secret, leaves the tree untouched --
def test_git_commit_refuses_a_secret_and_resets_staging(cfg):
    before = gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip()
    (cfg.root / "leak.txt").write_text(f"deploy key\n{PRIVATE_KEY}")
    with pytest.raises(ToolError) as exc:
        git_commit(cfg, {"message": "add deploy key"}, _tok())
    assert "refused" in str(exc.value) and "private key" in str(exc.value)
    assert PRIVATE_KEY not in str(exc.value)                 # never echoes the secret
    # HEAD did not move and nothing is left staged.
    assert gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip() == before
    staged = gitio.git("diff", "--cached", "--name-only", cwd=cfg.root, check=False)
    assert staged.strip() == ""


def test_git_commit_allows_clean_content(cfg):
    before = gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip()
    (cfg.root / "notes.md").write_text("# Notes\nA normal, secret-free file.\n")
    out = git_commit(cfg, {"message": "add notes"}, _tok())
    assert out["commit"] and out["commit"] != before
    assert gitio.git("rev-parse", "HEAD", cwd=cfg.root).strip() == out["commit"]


def test_git_commit_does_not_block_on_prior_history(cfg):
    # A secret already in a PRIOR commit must not block an unrelated new commit:
    # only ADDED lines are scanned.
    (cfg.root / "old.txt").write_text(f"legacy {AWS_KEY}")
    gitio.git("add", "old.txt", cwd=cfg.root)
    gitio.git("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-m", "legacy",
              cwd=cfg.root)
    (cfg.root / "new.txt").write_text("a clean addition")
    out = git_commit(cfg, {"message": "clean add"}, _tok())
    assert out["commit"]


# -- the write layer: flags but does not block a recoverable edit --
def test_file_write_flags_secret_content_without_blocking(cfg):
    out = file_write(cfg, {"path": "work/config.txt",
                           "content": f"aws_key={AWS_KEY}\n"}, _tok())
    assert (cfg.root / "work/config.txt").exists()           # write still happened
    assert "AWS" in out["secret_flagged"]                    # but it is flagged
    assert AWS_KEY not in out["secret_flagged"]


def test_file_write_clean_content_has_no_flag(cfg):
    out = file_write(cfg, {"path": "work/readme.txt", "content": "hello world"},
                     _tok())
    assert out["secret_flagged"] == ""
