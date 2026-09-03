"""Setup and preflight: the first use must not end in an error nobody can act on.

Five things a person meets before any audit has happened — the Gatekeeper
dialog, a task sent before a provider is connected, a same-vendor pair, a
silent first retry, and the wizard's GitHub default — each asserted from what
is shipped: the DMG scripts, the served page, the shipped server, the CLI's
own stderr, and the resilience layer's events.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.request
from dataclasses import replace
from pathlib import Path

import pytest

from crossaudit import app_keys
from crossaudit.cli import i18n
from crossaudit.cli import main as cli_main
from crossaudit.config import Resilience, Role, heterogeneity, load
from crossaudit.console import chats
from crossaudit.console import page as page_mod
from crossaudit.console import server as server_mod
from crossaudit.errors import ProviderDenial
from crossaudit.providers import resilience
from crossaudit.providers.base import Reply

ROOT = Path(__file__).resolve().parents[1]
HARNESS = Path(__file__).parent / "harness"
SRC = ROOT / "src"
CJK = re.compile(r"[一-鿿]")
PAGE = page_mod.PAGE

#: Every variable a credential could arrive through; cleared so the check
#: sees the machine a first-time user has, not the developer's shell.
KEY_ENVS = sorted({*app_keys.PROVIDER_ENVS.values(),
                   *app_keys.ROLE_FALLBACKS.values(),
                   *(app_keys.backup_env_for_vendor(v) for v in app_keys.PROVIDER_ENVS),
                   "CROSSAUDIT_AUDITOR_KEY", "CROSSAUDIT_GENERATOR_KEY"})


def _translate(values: list[str], tmp_path: Path) -> dict:
    """Render strings through the SHIPPED page translator (node)."""
    extracted = subprocess.run(
        [sys.executable, str(HARNESS / "extract_zh.py"), str(ROOT)],
        capture_output=True, text=True, check=True)
    driver = tmp_path / "zh.js"
    driver.write_text(extracted.stdout + "\nconst V=" + json.dumps(values)
                      + ";\nconsole.log(JSON.stringify(V.map(v=>zhValue(v))));")
    out = subprocess.run(["node", str(driver)], capture_output=True, text=True)
    assert out.returncode == 0, out.stderr
    return dict(zip(values, json.loads(out.stdout)))


@pytest.fixture(autouse=True)
def _no_credentials_in_reach(monkeypatch, tmp_path):
    for name in KEY_ENVS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.delenv("CROSSAUDIT_APP_MODE", raising=False)
    for name in ("LC_ALL", "LC_MESSAGES", "LANG"):
        monkeypatch.delenv(name, raising=False)
    # The keys file the CLI wizard writes lives under HOME; a developer's real
    # one must not leak into a test about having none.
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    # Presence only, and never the Keychain of the machine running the tests.
    monkeypatch.setattr(app_keys, "read", lambda *_a, **_k: "")
    yield
    i18n.set_language(i18n.DEFAULT_LANGUAGE)


def _project(root: Path, *, generator: str = "openai", auditor: str = "anthropic",
             auditor_provider: str = "replay") -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "experiments").mkdir(exist_ok=True)
    (root / "AUDIT_RULES.md").write_text("### CA-X-001\n**BLOCKER.** x\n\nx\n")
    (root / "crossaudit.yml").write_text(
        "version: 1\nscience_repo: t/p\nconstitution: AUDIT_RULES.md\n"
        f"auditor: {{vendor: {auditor}, provider: {auditor_provider}, model: m,"
        " key_env: CROSSAUDIT_AUDITOR_KEY}\n"
        f"generator: {{vendor: {generator}, provider: openai_compat, model: g}}\n"
        "scope: {dirs: [experiments]}\n"
        "ledger: {dir: cycles}\nstate: {dir: .crossaudit}\nchecks: [parseable]\n")
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x.invalid",
                    "add", "-A"], cwd=root, check=True)
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@x.invalid",
                    "commit", "-q", "-m", "bootstrap"], cwd=root, check=True)
    return root


# ------------------------------------------------------------ S1 Gatekeeper
def test_the_dmg_window_says_how_to_open_the_app_in_both_languages():
    """The first thing macOS does with an ad-hoc signed app is refuse it, and
    nothing inside the app can explain that — it has not run. The sentence
    sits beside the app, and the verifier refuses a DMG without it."""
    build = (ROOT / "packaging/macos/build_dmg.sh").read_text()
    verifier = (ROOT / "packaging/macos/verify_dmg.sh").read_text()
    assert '"$DMG_ROOT/如何打开 · How to open.txt"' in build
    assert "macOS may say the app can't be verified. Right-click CrossAudit.app → Open" in build
    assert "→ Open. This happens once." in build
    assert "右键点击 CrossAudit.app → 打开 → 打开" in build and "只需这样做一次" in build
    # The verifier's manifest of DMG notes: both, by name, non-empty.
    assert 'for note in "如何打开 · How to open.txt" "About the crossaudit command.txt"' in verifier
    assert 'DMG is missing the note' in verifier


def test_the_readme_leads_the_install_section_with_first_open_and_says_how_to_leave():
    readme = (ROOT / "README.md").read_text()
    install = readme.split("## Install", 1)[1].split("## Five-minute quick start", 1)[0]
    first_open = install.index("**First open.** macOS may say the app can't be verified.")
    assert first_open < install.index("1. Download `CrossAudit-"), (
        "the Gatekeeper instruction must come before the download steps")
    assert "Right-click\n> **CrossAudit.app** → **Open** → **Open**. This happens once." in install
    uninstall = install.split("### Uninstall / remove all data", 1)[1]
    for location in ("~/Library/Application Support/CrossAudit", "`.crossaudit/`",
                     "io.crossaudit.app.provider.<vendor>"):
        assert location in uninstall, location


def test_settings_privacy_lists_the_same_three_locations():
    pane = PAGE.split('data-settings-pane="security"', 1)[1].split("</section>", 1)[0]
    assert "Where CrossAudit keeps data" in pane
    for location in ("~/Library/Application Support/CrossAudit", ".crossaudit/",
                     "io.crossaudit.app.provider.&lt;vendor&gt;"):
        assert location in pane, location


# ------------------------------------------------------ S2 credential card
def test_the_app_answers_a_task_without_credentials_with_a_setup_card(tmp_path, monkeypatch):
    """Through the shipped server, in app mode: nothing starts, no chat is
    created, and the answer names the role and the one place to fix it —
    not an audit escalation and not a refusal sentence."""
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    cfg = load(_project(tmp_path / "p") / "crossaudit.yml")
    url, httpd = server_mod.serve(cfg, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    try:
        request = urllib.request.Request(
            url.replace("/?t=", "/api/say?t="),
            data=b'{"text": "build a demo"}', method="POST",
            headers={"content-type": "application/json"})
        with urllib.request.urlopen(request, timeout=20) as response:
            assert response.status == 200
            body = json.loads(response.read().decode("utf-8"))
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert body["setup"] == "credentials"
    assert body["missing"] == ["generator"], body
    assert body["action"] == "providers" and body["lane"] == "setup"
    assert "chat_id" not in body, "a message the app could not send leaves no thread"
    assert chats._read(cfg)["chats"] == []
    assert not (cfg.root / "TASK.md").exists(), "nothing was committed or started"


def test_the_card_names_whichever_role_is_unconnected(tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    cfg = load(_project(tmp_path / "p", auditor_provider="openai_compat") / "crossaudit.yml")
    assert server_mod.setup_needed(cfg)["missing"] == ["generator", "auditor"]
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "present")
    assert server_mod.setup_needed(cfg)["missing"] == ["auditor"]
    monkeypatch.setenv("CROSSAUDIT_AUDITOR_KEY", "present")
    assert server_mod.setup_needed(cfg) is None
    # The app's own presence API counts too: a key just written in Settings
    # is in the vendor's variable, whatever key_env the project names.
    monkeypatch.delenv("CROSSAUDIT_AUDITOR_KEY")
    monkeypatch.setenv("CROSSAUDIT_ANTHROPIC_KEY", "present")
    assert server_mod.setup_needed(cfg) is None


def test_outside_the_app_the_check_is_the_preflight_refusal(tmp_path):
    cfg = load(_project(tmp_path / "p") / "crossaudit.yml")
    assert server_mod.setup_needed(cfg) is None, "no Settings → Providers to open"
    from crossaudit.cli.build import missing_credentials, preflight
    from crossaudit.errors import ConfigDenial
    assert missing_credentials(cfg) == ["generator"]
    with pytest.raises(ConfigDenial) as caught:
        preflight(cfg)
    assert caught.value.reason.startswith("connect a provider first: the generator has no credential")


def test_page_markup_declares_the_setup_card_and_leaves_the_composer_alone():
    script = PAGE.split("<script>")[1]
    assert "if(r.setup==='credentials'){" in script
    assert "route.innerHTML=setupCardMarkup(r.missing||[])" in script
    assert "document.getElementById('setup-open-providers').onclick=()=>openSettings('providers')" in script
    branch = script.split("if(r.setup==='credentials'){", 1)[1].split("else if(r.asked)", 1)[0]
    assert "say.value=''" not in branch, "the composer keeps the message for resending"
    for text in ("<b>Connect a provider first</b>", "The generator has no credential yet.",
                 "The auditor has no credential yet.",
                 "Neither the generator nor the auditor has a credential yet.",
                 "Open Settings → Providers"):
        assert text in script, text


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_setup_card_reads_in_chinese(tmp_path):
    values = ["Connect a provider first", "The generator has no credential yet.",
              "The auditor has no credential yet.",
              "Neither the generator nor the auditor has a credential yet.",
              "Open Settings → Providers",
              "Recommended for shared or reviewed work; a single local project is fine to start.",
              "Where CrossAudit keeps data"]
    rendered = _translate(values, tmp_path)
    assert rendered["Connect a provider first"] == "请先连接供应商"
    assert rendered["The generator has no credential yet."] == "生成者尚未连接凭据。"
    assert rendered["Open Settings → Providers"] == "打开设置 → 供应商"
    for value in values:
        assert CJK.search(rendered[value]), f"reaches a Chinese reader in English: {value!r}"


def test_the_cli_refuses_before_the_loop_in_the_persons_language(tmp_path, monkeypatch, capsys):
    """`crossaudit build` under LANG=zh_CN.UTF-8: one plain sentence on stderr,
    nothing committed, no run started."""
    root = _project(tmp_path / "p")
    monkeypatch.chdir(root)
    before = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=root,
                            capture_output=True, text=True, check=True).stdout.strip()
    monkeypatch.setenv("LANG", "zh_CN.UTF-8")
    code = cli_main.main(["build", "make a thing"])
    err = capsys.readouterr().err
    assert code != 0
    assert "DENIED (config): 请先连接供应商：生成者没有凭据（`crossaudit doctor` 会提示输入）" in err, err
    assert "I1" not in err and "key_env" not in err
    after = subprocess.run(["git", "rev-list", "--count", "HEAD"], cwd=root,
                           capture_output=True, text=True, check=True).stdout.strip()
    assert before == after, "the task must not be committed before preflight passes"
    assert not (root / ".crossaudit" / "runtime.sqlite3").exists()

    monkeypatch.delenv("LANG")
    cli_main.main(["build", "make a thing"])
    assert ("DENIED (config): connect a provider first: the generator has no credential"
            in capsys.readouterr().err)


def test_both_roles_missing_is_one_sentence_in_both_languages(tmp_path):
    from crossaudit.cli.build import credential_preflight
    from crossaudit.errors import ConfigDenial
    cfg = load(_project(tmp_path / "p", auditor_provider="openai_compat") / "crossaudit.yml")
    with pytest.raises(ConfigDenial) as caught:
        credential_preflight(cfg)
    reason = caught.value.reason
    assert reason.startswith("connect a provider first: neither the generator nor the auditor")
    assert i18n.denial_zh(reason) == "请先连接供应商：生成者与审计者都没有凭据（`crossaudit doctor` 会提示输入）"


# ------------------------------------------------------- S3 same-vendor pair
def test_the_same_vendor_sentence_is_plain_and_the_invariant_name_is_not_in_it(tmp_path):
    cfg = load(_project(tmp_path / "p", generator="openai", auditor="openai") / "crossaudit.yml")
    ok, why = heterogeneity(cfg)
    assert ok is False
    assert why == ("The generator and the auditor must use different providers — "
                   "independent review is the core of the protocol. Change one of them "
                   "in Project controls. Their routes overlap at openai.")
    zh = i18n.denial_zh(why)
    assert zh == ("生成者与审计者必须使用不同的供应商——独立审查是协议的核心。"
                  "请在项目控制里更改其中一个。两者的路由在 openai 处重叠。")


def test_the_jargon_is_absent_from_every_user_facing_string():
    """`I1 violated` and `recovery pools overlap` reached the CLI, the console's
    project controls and the doctor. Nowhere a person reads, now."""
    for path in sorted(SRC.rglob("*.py")):
        text = path.read_text()
        assert "I1 violated" not in text, path
        assert "recovery pools overlap" not in text, path
    assert "I1 violated" not in PAGE
    for english, chinese in __import__("crossaudit.cli.denials_zh", fromlist=["ENTRIES"]).ENTRIES:
        assert "I1" not in english and "I1" not in chinese, english


# ------------------------------------------------------- S4 first retry seen
def _reply() -> Reply:
    return Reply("ok", "request", "a" * 64, "b" * 64,
                 {"usage": {"prompt_tokens": 2, "completion_tokens": 1}})


def test_the_first_attempt_after_a_failed_turn_is_narrated(cfg, monkeypatch):
    """The narration used to begin at attempt 2 or on a fallback route, so a
    turn that failed and the next turn's first try — the person's first
    retry — passed in silence. Mutation: restore the guard to
    `attempt > 1 or index > 0` in resilience.complete — the second call
    below emits nothing and this goes red."""
    primary = Role("primary", "model-a", "openai", "PRIMARY_KEY")
    cfg = replace(cfg, resilience=Resilience(
        max_attempts=1, initial_backoff_seconds=1, max_backoff_seconds=4,
        retry_after_cap_seconds=9, circuit_breaker_failures=5,
        circuit_breaker_cooldown_seconds=30))
    monkeypatch.setenv("PRIMARY_KEY", "secret-a")
    outcomes = iter(["busy", "ok", "ok"])
    events: list[tuple] = []

    def provider(_name):
        def complete(**_kwargs):
            if next(outcomes) == "busy":
                raise ProviderDenial("busy", status=429, category="rate_limit",
                                     retryable=True, retry_after_seconds=1)
            return _reply()
        return complete

    monkeypatch.setattr(resilience, "get_provider", provider)
    monkeypatch.setattr(resilience, "_sleep", lambda *_: None)
    call = lambda: resilience.complete(  # noqa: E731
        cfg, "generator", primary, system="s", prompt="p",
        on_event=lambda *row: events.append(row))

    with pytest.raises(ProviderDenial):
        call()                                    # turn 1: fails, no retry left
    assert [row[1] for row in events] == [], "a healthy-looking first try stays quiet"
    call()                                        # turn 2: the person's first retry
    assert events == [("generator", "provider recovery", "openai:model-a · attempt 1")]
    events.clear()
    call()                                        # turn 3: recovered; quiet again
    assert events == []


# ------------------------------------------------------- S5 wizard default
def test_two_repositories_is_off_by_default_and_explained():
    """A first project should not need GitHub. The line that says why it
    might is kept; the box is not pre-ticked."""
    toggle = re.search(r'<input type="checkbox" name="github" id="github-toggle"([^>]*)>', PAGE)
    assert toggle and "checked" not in toggle.group(1), toggle.group(0)
    assert ("Recommended for shared or reviewed work; a single local project is fine "
            "to start.") in PAGE
    # A restored draft that never said "github: true" stays local too.
    assert "document.getElementById('github-toggle').checked=draft.github===true;" in PAGE
