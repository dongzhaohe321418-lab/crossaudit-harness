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
    assert "macOS may say the app can't be verified — right-click CrossAudit.app → Open" in build
    assert "→ Open. This happens once." in build
    assert "右键点击 CrossAudit.app → 打开 → 打开" in build and "只需这样做一次" in build
    # The verifier's manifest of DMG notes: both, by name, non-empty.
    assert 'for note in "如何打开 · How to open.txt" "About the crossaudit command.txt"' in verifier
    assert 'DMG is missing the note' in verifier


def test_the_readme_leads_the_install_section_with_first_open_and_says_how_to_leave():
    readme = (ROOT / "README.md").read_text()
    install = readme.split("## Install", 1)[1].split("## Five-minute quick start", 1)[0]
    first_open = install.index("**First open.** macOS may say the app can't be verified")
    assert first_open < install.index("1. Download `CrossAudit-"), (
        "the Gatekeeper instruction must come before the download steps")
    assert "right-click\n> **CrossAudit.app** → **Open** → **Open**. This happens once." in install
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
    # A human generator writes its own commits and has no provider to connect;
    # only the auditor can be missing. Mutation: drop the `!= "human"` clause
    # in missing_credentials — the first assertion below names the generator.
    monkeypatch.delenv("CROSSAUDIT_ANTHROPIC_KEY")
    for spelling in ("human", "Human"):
        human = load(_project(tmp_path / spelling, generator=spelling,
                              auditor_provider="openai_compat") / "crossaudit.yml")
        assert server_mod.setup_needed(human)["missing"] == ["auditor"], spelling
    monkeypatch.setenv("CROSSAUDIT_ANTHROPIC_KEY", "present")
    assert server_mod.setup_needed(human) is None


def test_say_itself_refuses_to_route_without_credentials(tmp_path, monkeypatch):
    """The direct callers' guard (mutation: delete the `setup_needed` block at
    the top of `say()` — routing then asks the auditor, and this is red)."""
    from crossaudit import router as router_mod

    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setattr(router_mod, "route_addressed",
                        lambda *_a, **_k: pytest.fail("nothing may be routed first"))
    cfg = load(_project(tmp_path / "p") / "crossaudit.yml")
    result = server_mod.say(cfg, "build a demo", chat_id="")
    assert result["setup"] == "credentials" and result["missing"] == ["generator"]


def test_an_exported_generator_provider_never_re_arms_the_demo(tmp_path, monkeypatch):
    """The credential-free demo (both roles `replay`) is the door that must
    always open; a developer's CROSSAUDIT_GENERATOR_PROVIDER cannot shut it."""
    from crossaudit.cli.build import missing_credentials

    root = _project(tmp_path / "demo", auditor_provider="replay")
    config = root / "crossaudit.yml"
    config.write_text(config.read_text().replace(
        "generator: {vendor: openai, provider: openai_compat, model: g}",
        "generator: {vendor: openai, provider: replay, model: g}"))
    cfg = load(config)
    assert missing_credentials(cfg) == []
    monkeypatch.setenv("CROSSAUDIT_GENERATOR_PROVIDER", "openai_compat")
    assert missing_credentials(cfg) == [], "the override must not demand a key"
    # A project whose configured provider does need a key still honours it.
    keyed = load(_project(tmp_path / "keyed") / "crossaudit.yml")
    assert missing_credentials(keyed) == ["generator"]


def test_outside_the_app_the_check_is_the_preflight_refusal(tmp_path):
    cfg = load(_project(tmp_path / "p") / "crossaudit.yml")
    assert server_mod.setup_needed(cfg) is None, "no Settings → Providers to open"
    from crossaudit.cli.build import missing_credentials, preflight
    from crossaudit.errors import ConfigDenial
    assert missing_credentials(cfg) == ["generator"]
    with pytest.raises(ConfigDenial) as caught:
        preflight(cfg)
    assert caught.value.reason.startswith("connect a provider first: the generator has no credential")
    # The auditor-only shape (mutation: replace its raise with a bare return).
    monkeypatch_env = __import__("os").environ
    monkeypatch_env["CROSSAUDIT_GENERATOR_KEY"] = "present"
    try:
        auditor_only = load(_project(tmp_path / "a", auditor_provider="openai_compat")
                            / "crossaudit.yml")
        assert missing_credentials(auditor_only) == ["auditor"]
        with pytest.raises(ConfigDenial) as denied:
            preflight(auditor_only)
    finally:
        monkeypatch_env.pop("CROSSAUDIT_GENERATOR_KEY", None)
    assert denied.value.reason == ("connect a provider first: the auditor has no credential "
                                   "(`crossaudit doctor` will ask for it)")
    assert i18n.denial_zh(denied.value.reason) == (
        "请先连接供应商：审计者没有凭据（`crossaudit doctor` 会提示输入）")


def test_page_markup_declares_the_setup_card_and_leaves_the_composer_alone():
    script = PAGE.split("<script>")[1]
    assert "if(r.setup==='credentials'){" in script
    branch = script.split("if(r.setup==='credentials'){", 1)[1].split("else if(r.asked)", 1)[0]
    assert "showSetupCard(r.missing||[])" in branch
    assert "say.value=''" not in branch, "the composer keeps the message for resending"
    card = script.split("function showSetupCard(missing){", 1)[1].split("\nfunction ", 1)[0]
    assert "route.innerHTML=setupCardMarkup(missing)" in card
    assert "document.getElementById('setup-open-providers').onclick=()=>openSettings('providers')" in card
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
    assert rendered["The generator has no credential yet."] == "生成者还没有配置凭据。"
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
                   "independent review is the core of the protocol. Change one "
                   "in crossaudit.yml; their routes overlap at openai.")
    assert i18n.denial_zh(why) == (
        "生成者与审计者必须使用不同的供应商——独立审查是协议的核心。"
        "请在 crossaudit.yml 里更改其中一个；两者的路由在 openai 处重叠。")
    ok, console_why = heterogeneity(cfg, "console")
    assert ok is False
    assert console_why == ("The generator and the auditor must use different providers — "
                           "independent review is the core of the protocol. Change one "
                           "in Project controls; their routes overlap at openai.")
    assert i18n.denial_zh(console_why) == (
        "生成者与审计者必须使用不同的供应商——独立审查是协议的核心。"
        "请在项目控制里更改其中一个；两者的路由在 openai 处重叠。")
    for sentence in (why, console_why):
        assert sentence.count(". ") + 1 <= 2, "two sentences at most"
    # The console's own path (Project controls → runtime update) and the
    # console's build entry speak the console variant; the CLI the file.
    from crossaudit.cli.build import preflight
    from crossaudit.errors import ConfigDenial
    with pytest.raises(ConfigDenial) as cli_denied:
        preflight(cfg)
    assert "crossaudit.yml" in cli_denied.value.reason
    with pytest.raises(ConfigDenial) as console_denied:
        preflight(cfg, "console")
    assert "Project controls" in console_denied.value.reason


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
    assert events == [("generator", "Retrying the generator's provider · attempt 1",
                       "openai:model-a")]
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


# ------------------------------------- S2 the other ways a build can start
def _serve(cfg):
    url, httpd = server_mod.serve(cfg, port=0)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return url, httpd


def _post(url: str, path: str, body: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        url.replace("/?t=", path + "?t="), data=json.dumps(body).encode(),
        method="POST", headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as denied:
        return denied.code, json.loads(denied.read().decode("utf-8"))


def test_a_provider_retry_without_credentials_is_the_setup_card_not_an_escalation(
        tmp_path, monkeypatch):
    """/api/escalation retry_provider, through the shipped handler in app
    mode: the same card, the cycle left as it was, and nothing written to the
    ledger as a provider failure."""
    from crossaudit.controller import StateStore

    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    cfg = load(_project(tmp_path / "p") / "crossaudit.yml")
    store = StateStore(cfg.root / cfg.state_dir / "state.json")
    stopped = store.record_build_escalation(
        "t/p", "c" * 40, "generator provider failure in round 1: subscription unavailable",
        1, "history", "Create one accurate review")
    before = store.cycle(stopped["cycle_id"])
    monkeypatch.setattr(server_mod, "start_build",
                        lambda *_a, **_k: pytest.fail("nothing may start"))
    url, httpd = _serve(cfg)
    try:
        status, body = _post(url, "/api/escalation", {
            "cycle_id": stopped["cycle_id"], "action": "retry_provider", "reason": ""})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200 and body["setup"] == "credentials"
    assert body["missing"] == ["generator"] and body["action"] == "providers"
    after = store.cycle(stopped["cycle_id"])
    assert after["status"] == "ESCALATED" and after == before, "left exactly as it was"
    assert "could not start" not in json.dumps(after)
    assert "crossaudit doctor" not in json.dumps(body), "no terminal command in the app"


def test_an_interrupted_task_retry_without_credentials_is_the_setup_card(
        tmp_path, monkeypatch):
    """/api/interrupted retry, through the shipped handler in app mode."""
    from crossaudit.console import daemon
    from crossaudit.runtime import RunJournal, journal_path

    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    cfg = load(_project(tmp_path / "p") / "crossaudit.yml")
    RunJournal(journal_path(cfg)).start("cut off mid-round", owner_pid=999999)
    assert daemon.interrupted(cfg)
    monkeypatch.setattr(server_mod, "start_build",
                        lambda *_a, **_k: pytest.fail("nothing may start"))
    url, httpd = _serve(cfg)
    try:
        status, body = _post(url, "/api/interrupted", {"action": "retry"})
    finally:
        httpd.shutdown()
        httpd.server_close()
    assert status == 200 and body["setup"] == "credentials"
    assert body["missing"] == ["generator"]
    assert daemon.interrupted(cfg), "the interruption is still there to retry"
    assert "crossaudit doctor" not in json.dumps(body)


def test_every_build_entry_point_in_the_server_asks_setup_needed_first():
    """Structural guard for the ruling: no `start_build(` call in the handler
    without a `setup_needed` check on its path. Enumerated from the source so
    a new entry point lands here because it is written."""
    source = Path(server_mod.__file__).read_text()
    handler = source.split("def make_handler(", 1)[1]
    calls = [m.start() for m in re.finditer(r"start_build\(", handler)]
    assert len(calls) >= 2, "the handler's retry paths moved"
    for position in calls:
        window = handler[max(0, position - 1500):position]
        assert "setup_needed(current)" in window, handler[position - 200:position]
    # say() guards its own generator lane at the top.
    say_body = source.split("def say(", 1)[1].split("\ndef ", 1)[0]
    assert say_body.index("blocked = setup_needed(cfg)") < say_body.index("start_build(")


def test_page_markup_declares_the_card_on_the_retry_paths_too():
    script = PAGE.split("<script>")[1]
    escalation = script.split("const r=await api('/api/escalation'", 1)[1][:400]
    assert "r.setup==='credentials'" in escalation and "showSetupCard(" in escalation
    interrupted = script.split("const r=await api('/api/interrupted'", 1)[1][:400]
    assert "r.setup==='credentials'" in interrupted and "showSetupCard(" in interrupted
    assert ".route.setup{background:var(--accent-bg)" in PAGE
    assert "--escalated" not in PAGE.split(".route.setup{", 1)[1].split("}", 1)[0]


# ------------------------------------- S4 every retry sentence, in Chinese
def _drive_every_emitter(cfg, monkeypatch) -> list[tuple[str, str, str]]:
    """Run resilience.complete through the states that reach each of its
    on_event call sites: a retry on the primary, a fallback that connects, a
    fallback without a credential, a primary without a credential."""
    events: list[tuple] = []
    cfg = replace(cfg, resilience=Resilience(
        max_attempts=2, initial_backoff_seconds=1, max_backoff_seconds=4,
        retry_after_cap_seconds=9, circuit_breaker_failures=5,
        circuit_breaker_cooldown_seconds=30))
    monkeypatch.setattr(resilience, "_sleep", lambda *_: None)
    monkeypatch.setattr(resilience.random, "uniform", lambda *_: 1.0)
    monkeypatch.setenv("PRIMARY_KEY", "secret-a")
    monkeypatch.setenv("BACKUP_KEY", "secret-b")
    calls: list[str] = []

    def provider(name):
        def complete(**_kwargs):
            calls.append(name)
            if name == "primary":
                raise ProviderDenial("busy", status=429, category="rate_limit",
                                     retryable=True, retry_after_seconds=2)
            return _reply()
        return complete

    monkeypatch.setattr(resilience, "get_provider", provider)
    on_event = lambda *row: events.append(row)  # noqa: E731
    with_backup = Role("primary", "model-a", "openai", "PRIMARY_KEY",
                       fallbacks=(Role("backup", "model-b", "google", "BACKUP_KEY"),))
    resilience.complete(cfg, "generator", with_backup, system="s", prompt="p",
                        on_event=on_event)
    monkeypatch.delenv("BACKUP_KEY")
    with pytest.raises(ProviderDenial):
        resilience.complete(cfg, "auditor", with_backup, system="s", prompt="p",
                            on_event=on_event)
    monkeypatch.delenv("PRIMARY_KEY")
    with pytest.raises(ProviderDenial):
        resilience.complete(cfg, "generator", Role("primary", "model-a", "openai",
                                                   "PRIMARY_KEY"),
                            system="s", prompt="p", on_event=on_event)
    return events


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_every_retry_sentence_the_emitters_can_say_reaches_a_chinese_reader(
        cfg, monkeypatch, tmp_path):
    """Through the emitters, not a hand list: every `on_event(` call site in
    resilience.py is exercised, and each sentence it produced comes back
    Chinese from BOTH seams — the server's phase projection (what the run
    card reads as text_i18n) and the page translator (the walker-driven
    surfaces) — with no provider:model on the sentence."""
    from crossaudit.console.progress import concise_detail, phase_i18n

    events = _drive_every_emitter(cfg, monkeypatch)
    sentences = sorted({row[1] for row in events})
    source = Path(resilience.__file__).read_text()
    shapes = {re.sub(r"\d+(\.\d+)?", "N", s).replace("generator", "ROLE")
              .replace("auditor", "ROLE") for s in sentences}
    assert len(shapes) == source.count("on_event(role_name") + 1, (
        "an emitter was not driven, or one emits two shapes", shapes)
    rendered = _translate(sentences, tmp_path)
    for sentence in sentences:
        assert not re.search(r"\S+:\S+", sentence), sentence     # words, not routes
        assert CJK.search(phase_i18n(sentence)["zh"]), ("server seam", sentence)
        assert phase_i18n(sentence)["zh"] != sentence
        assert CJK.search(rendered[sentence]), ("page seam", sentence)
        assert rendered[sentence] == phase_i18n(sentence)["zh"], sentence
    assert phase_i18n("Retrying the generator's provider · attempt 2")["zh"] == (
        "正在重试生成者的供应商 · 第 2 次")
    # The route identity rides in the detail and the projection drops it.
    routes = [row[2] for row in events if re.fullmatch(r"\S+:\S+", row[2])]
    assert routes, "the identifiers moved out of the detail"
    assert all(concise_detail("provider_recovery", d) == "" for d in routes)
