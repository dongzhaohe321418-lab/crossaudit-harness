from __future__ import annotations

import importlib
import json
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from crossaudit import _selfid, app, app_keys, workspace
from crossaudit.auditor import run as auditor_run
from crossaudit.config import load
from crossaudit.console import projects
from crossaudit.constitution import Draft, Rule
from crossaudit.errors import ConfigDenial
from crossaudit.providers.specs import SPECS


def app_payload(**changes):
    value = {
        "name": "desktop-demo",
        "description": "Create exactly one readable project review with no unsupported claims.",
        "project_type": "general",
        "max_rounds": 3,
        "auditor_vendor": "openai",
        "auditor_model": "gpt-5.6-sol",
        "generator_vendor": "anthropic",
        "generator_model": "claude-sonnet-4-6",
        "github": False,
    }
    value.update(changes)
    return value


def test_keychain_write_never_places_secret_in_process_arguments(monkeypatch):
    calls = []

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(app_keys.subprocess, "run", run)
    monkeypatch.setattr(app_keys, "_security", lambda: "/usr/bin/security")
    monkeypatch.setattr(app_keys, "_account", lambda: "tester")
    app_keys.write("openai", "test-only-secret")

    args, kwargs = calls[0]
    assert "test-only-secret" not in args
    assert kwargs["input"] == "test-only-secret\ntest-only-secret\n"
    assert os.environ["CROSSAUDIT_OPENAI_KEY"] == "test-only-secret"


def test_settings_response_reports_presence_but_never_secret(monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "private-openai")
    monkeypatch.setenv("CROSSAUDIT_ANTHROPIC_KEY", "private-anthropic")

    result = app_keys.apply({})

    encoded = json.dumps(result)
    assert result["providers"]["openai"]["configured"]
    assert result["providers"]["anthropic"]["configured"]
    assert "private-openai" not in encoded and "private-anthropic" not in encoded


def test_backup_key_uses_an_independent_write_only_keychain_slot(monkeypatch):
    calls = []
    monkeypatch.delenv("CROSSAUDIT_OPENAI_BACKUP_KEY", raising=False)

    def run(args, **kwargs):
        calls.append((args, kwargs))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(app_keys.subprocess, "run", run)
    monkeypatch.setattr(app_keys, "_security", lambda: "/usr/bin/security")
    monkeypatch.setattr(app_keys, "_account", lambda: "tester")
    result = app_keys.apply({"openai_backup_key": "backup-only-secret"})

    assert any(str(item).endswith(".openai.backup") for item in calls[0][0])
    assert "backup-only-secret" not in calls[0][0]
    assert result["providers"]["openai"]["backup_configured"] is True
    assert "backup-only-secret" not in json.dumps(result)


def test_settings_exposes_every_first_party_provider_without_a_secret(monkeypatch):
    for vendor, spec in SPECS.items():
        monkeypatch.setenv(spec.key_env, f"private-{vendor}")
    result = app_keys.apply({})
    encoded = json.dumps(result)
    assert set(result["providers"]) == set(SPECS)
    assert all(row["configured"] for row in result["providers"].values())
    assert "private-" not in encoded


def test_app_bootstrap_creates_a_clean_hidden_controller(tmp_path):
    workspace = tmp_path / "CrossAudit Projects"
    workspace.mkdir()

    root = app._controller_project(workspace)
    cfg = load(root / "crossaudit.yml")

    assert root.name == ".crossaudit-home"
    assert cfg.auditor.key_env == "CROSSAUDIT_OPENAI_KEY"
    assert cfg.generator_key_env == "CROSSAUDIT_ANTHROPIC_KEY"
    assert cfg.scope_dirs == ["work"]
    assert not (root / "work").exists()
    assert subprocess.run(["git", "status", "--porcelain"], cwd=root,
                          capture_output=True, text=True, check=True).stdout == ""


def test_packaged_runtime_self_test_is_isolated_and_exercises_documents(
        tmp_path, monkeypatch):
    support = tmp_path / "real-support-must-stay-empty"
    monkeypatch.setenv("CROSSAUDIT_APP_SUPPORT", str(support))

    result = app.self_test()

    assert result["ok"] is True
    assert result["loopback_token_enforced"] is True
    assert result["documents"]["pdf"]["bytes"] > 100
    assert result["documents"]["docx"]["bytes"] > 100
    assert result["tls"]["trusted_certificate_authorities"] > 0
    assert len(result["dcl_source_sha256"]) == 64
    assert not support.exists()


def test_packaged_runtime_self_test_has_a_machine_readable_cli(monkeypatch, capsys):
    monkeypatch.setattr(app.sys, "argv", ["CrossAuditCore", "--self-test"])
    monkeypatch.setattr(app, "self_test", lambda: {"ok": True, "version": "test"})

    assert app.main() == 0
    assert json.loads(capsys.readouterr().out) == {"ok": True, "version": "test"}


def test_packaged_runtime_self_test_fails_closed_without_a_traceback(
        monkeypatch, capsys):
    monkeypatch.setattr(app.sys, "argv", ["CrossAuditCore", "--self-test"])
    monkeypatch.setattr(app, "self_test",
                        lambda: (_ for _ in ()).throw(RuntimeError("broken runtime")))

    assert app.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert json.loads(output.err) == {
        "ok": False, "error": "RuntimeError", "detail": "broken runtime"}


def test_self_test_mode_is_selected_by_argv_prefix_for_future_flags(
        monkeypatch, capsys):
    monkeypatch.setattr(app, "self_test", lambda: {"ok": True, "future": True})

    assert app.main(["--self-test", "--future-release-check"]) == 0
    assert json.loads(capsys.readouterr().out) == {"future": True, "ok": True}


def test_frozen_entry_help_and_version_are_finite_informational_modes(
        monkeypatch, capsys):
    monkeypatch.setattr(
        app, "_run_app",
        lambda: pytest.fail("informational arguments must not start app mode"))

    assert app.main(["--help"]) == 0
    help_output = capsys.readouterr()
    assert "usage: crossaudit" in help_output.out
    assert "doctor" in help_output.out
    assert "init" in help_output.out
    assert "build" in help_output.out
    assert help_output.err == ""

    assert app.main(["--version"]) == 0
    version_output = capsys.readouterr()
    assert version_output.out.startswith(
        f"crossaudit {app.__version__} (receipt schema ")
    assert version_output.err == ""


def test_bare_frozen_entry_is_the_only_implicit_app_mode(monkeypatch, capsys):
    monkeypatch.setattr(app, "_run_app", lambda: 9)

    assert app.main([]) == 9
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err == ""


@pytest.mark.parametrize("argv,expected", [
    (["--unknown"], 2),
    (["ordinary-folder"], 2),
    (["--project-console"], 20),
    (["--project-console", "one", "two", "three"], 20),
    (["--project-console", "one", "not-a-port"], 20),
    (["--project-console", "one", "65536"], 20),
])
def test_every_non_mode_argument_shape_is_a_visible_refusal_not_app_mode(
        argv, expected, monkeypatch, capsys):
    monkeypatch.setattr(
        app, "_run_app",
        lambda: pytest.fail("arguments must never fall through to app mode"))

    assert app.main(argv) == expected
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err
    assert "Traceback" not in output.err


def test_every_public_cli_command_reaches_the_existing_cli_main(
        monkeypatch, capsys):
    cli_module = importlib.import_module("crossaudit.cli.main")
    parser = cli_module.build_parser()
    verbs = next(
        action.choices for action in parser._actions  # noqa: SLF001 -- contract enumeration
        if getattr(action, "choices", None) and action.dest == "verb")
    observed = []
    monkeypatch.setattr(cli_module, "main", lambda argv: observed.append(argv) or 73)
    monkeypatch.setattr(
        app, "_run_app",
        lambda: pytest.fail("a CLI command must never start app mode"))

    for verb in verbs:
        assert app.main([verb]) == 73

    assert observed == [[verb] for verb in verbs]
    assert set(verbs) == {
        "init", "run", "doctor", "check", "audit", "verify",
        "export-pubkey", "reproduce", "status", "watch", "skills",
        "console", "pair", "build", "talk", "routing", "amend", "resolve",
    }
    assert capsys.readouterr().err == ""


def test_cli_dispatch_guard_goes_red_if_a_public_command_falls_back_to_app(
        monkeypatch):
    cli_module = importlib.import_module("crossaudit.cli.main")
    reached = []
    monkeypatch.setattr(cli_module, "main", lambda argv: reached.append(argv) or 0)
    monkeypatch.setattr(app, "_run_app", lambda: 0)

    def exercise() -> None:
        reached.clear()
        assert app.main(["doctor"]) == 0
        assert reached == [["doctor"]], "doctor did not reach cli.main"

    exercise()
    with monkeypatch.context() as mutant:
        original = app._dispatch
        mutant.setattr(
            app, "_dispatch",
            lambda argv: app._run_app() if argv == ["doctor"] else original(argv))
        with pytest.raises(AssertionError, match="did not reach cli.main"):
            exercise()


def test_project_console_dispatch_accepts_only_its_explicit_shape(
        tmp_path, monkeypatch, capsys):
    observed = []
    monkeypatch.setattr(
        app, "project_console",
        lambda root, port=0: observed.append((root, port)) or 7)

    assert app.main(["--project-console", str(tmp_path), "4321"]) == 7
    assert observed == [(Path(str(tmp_path)), 4321)]
    assert capsys.readouterr().err == ""


def test_frozen_project_console_refuses_a_non_project_without_a_traceback(
        tmp_path, capsys):
    empty = tmp_path / "ordinary folder"
    empty.mkdir()

    assert app.main(["--project-console", str(empty)]) == 20
    output = capsys.readouterr()
    assert output.out == ""
    assert output.err.startswith("DENIED (config): no crossaudit.yml found")
    assert "crossaudit init" in output.err
    assert "Traceback" not in output.err


@pytest.mark.parametrize("phase,expected", [
    ("support", "private application data"),
    ("workspace", "create its workspace"),
    ("keys", "saved connection settings"),
    ("controller", "create its workspace"),
    ("config", "create its workspace"),
    ("bind", "private local console"),
])
def test_every_app_startup_precondition_is_inside_the_no_traceback_boundary(
        tmp_path, monkeypatch, capsys, phase, expected):
    for name in ("CROSSAUDIT_APP_MODE", "CROSSAUDIT_APP_SUPPORT",
                 "CROSSAUDIT_WORKSPACE_ROOT"):
        monkeypatch.setenv(name, "")
    support = tmp_path / "support"
    workspace = tmp_path / "workspace"
    if phase == "support":
        support.write_text("not a directory", encoding="utf-8")
    if phase == "workspace":
        workspace.write_text("not a directory", encoding="utf-8")
    monkeypatch.setattr(app, "app_support", lambda: support)
    monkeypatch.setattr(app, "workspace_root", lambda _support: workspace)
    monkeypatch.setattr(app, "load_into_environment", lambda: None)
    monkeypatch.setattr(
        app, "_controller_project", lambda root: root / ".crossaudit-home")
    monkeypatch.setattr(app, "load", lambda _path: object())
    monkeypatch.setattr(
        app, "serve",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            PermissionError("bind internals")))
    if phase == "keys":
        monkeypatch.setattr(
            app, "load_into_environment",
            lambda: (_ for _ in ()).throw(PermissionError("key internals")))
    elif phase == "controller":
        monkeypatch.setattr(
            app, "_controller_project",
            lambda _root: (_ for _ in ()).throw(
                PermissionError("controller internals")))
    elif phase == "config":
        monkeypatch.setattr(
            app, "load",
            lambda _path: (_ for _ in ()).throw(
                PermissionError("config internals")))

    assert app.main([]) == 20
    output = capsys.readouterr()
    combined = output.out + output.err
    assert expected in combined
    assert "Traceback (most recent call last)" not in combined
    assert "internals" not in combined


@pytest.mark.parametrize("fixture", ["missing_workspace", "existing_workspace"])
def test_unwritable_workspace_fixtures_return_an_actionable_denial(
        tmp_path, monkeypatch, capsys, fixture):
    if os.name == "nt" or (hasattr(os, "geteuid") and os.geteuid() == 0):
        pytest.skip("requires ordinary POSIX directory permissions")
    for name in ("CROSSAUDIT_APP_MODE", "CROSSAUDIT_APP_SUPPORT",
                 "CROSSAUDIT_WORKSPACE_ROOT"):
        monkeypatch.setenv(name, "")
    support = tmp_path / "support"
    parent = tmp_path / "Documents"
    parent.mkdir()
    workspace = parent / "CrossAudit Projects"
    locked = parent
    if fixture == "existing_workspace":
        workspace.mkdir()
        locked = workspace
    monkeypatch.setattr(app, "app_support", lambda: support)
    monkeypatch.setattr(app, "workspace_root", lambda _support: workspace)
    monkeypatch.setattr(app, "load_into_environment", lambda: None)
    locked.chmod(0o500)
    try:
        assert app.main([]) == 20
    finally:
        locked.chmod(0o700)

    output = capsys.readouterr()
    combined = output.out + output.err
    assert "CrossAudit could not create its workspace" in combined
    assert "Privacy & Security › Files and Folders" in combined
    assert "choose another location" in combined
    assert "Traceback (most recent call last)" not in combined


def test_frozen_entry_exception_guard_goes_red_when_the_real_boundary_is_removed(
        tmp_path, monkeypatch, capsys):
    """D10: bypassing the production boundary fails the no-traceback guard."""
    internal = "/private/build/crossaudit/config.py"
    monkeypatch.setattr(
        app, "project_console",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            FileNotFoundError(internal)))

    def exercise() -> None:
        leaked = None
        result = None
        try:
            result = app.main(["--project-console", str(tmp_path)])
        except Exception as exc:  # the assertion records a boundary leak as red
            leaked = exc
        assert leaked is None, (
            f"frozen entry leaked {type(leaked).__name__}: {leaked}")
        assert result == 20

    exercise()
    safe_output = capsys.readouterr()
    assert "Traceback" not in safe_output.err
    assert internal not in safe_output.err

    with monkeypatch.context() as mutant:
        mutant.setattr(app, "_entry_boundary", lambda operation: operation())
        with pytest.raises(AssertionError, match="leaked FileNotFoundError"):
            exercise()


def test_app_workspace_override_is_trusted_process_state(tmp_path, monkeypatch, cfg):
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(tmp_path))
    assert projects.workspace_base(cfg) == tmp_path.resolve()


def test_native_workspace_choice_persists_across_app_restarts(tmp_path, monkeypatch):
    support = tmp_path / "support"
    selected = tmp_path / "My Projects"
    another = tmp_path / "Client Projects"
    selected.mkdir()
    another.mkdir()
    # Track the process override before select_workspace changes it directly,
    # so pytest restores the caller's original environment after this test.
    monkeypatch.setenv("CROSSAUDIT_WORKSPACE_ROOT", str(tmp_path / "original"))

    chosen = workspace.select_workspace(support, str(selected))
    workspace.select_workspace(support, str(another))
    assert chosen == selected.resolve()
    assert not list(selected.glob(".crossaudit-write-test-*"))
    if os.name != "nt":
        assert (support / workspace.SETTINGS_NAME).stat().st_mode & 0o777 == 0o600

    monkeypatch.delenv("CROSSAUDIT_WORKSPACE_ROOT", raising=False)
    assert app.workspace_root(support) == another.resolve()
    assert workspace.known_workspaces(support) == (
        selected.resolve(), another.resolve())


def test_workspace_choice_refuses_a_missing_path_with_ui_action(tmp_path):
    with pytest.raises(ConfigDenial) as caught:
        workspace.select_workspace(tmp_path / "support", str(tmp_path / "missing"))
    assert caught.value.detail == {
        "issue": "workspace_missing", "action": "choose_workspace"}


def test_native_shell_exposes_only_the_local_workspace_picker_bridge():
    source = (Path(__file__).parents[1] / "packaging" / "macos" /
              "CrossAuditApp.swift").read_text()
    assert "WKScriptMessageHandler" in source
    assert 'action == "chooseWorkspace"' in source
    assert 'action == "revealInFinder"' in source
    assert "activateFileViewerSelecting" in source
    assert '["127.0.0.1", "localhost"]' in source
    assert "message.frameInfo.isMainFrame" in source
    assert "canChooseDirectories = true" in source
    assert "canChooseFiles = false" in source
    assert "DispatchSource.makeSignalSource" in source
    assert "[SIGINT, SIGTERM]" in source


def test_native_shell_has_bounded_startup_recovery_and_log_retention():
    source = (Path(__file__).parents[1] / "packaging" / "macos" /
              "CrossAuditApp.swift").read_text()
    assert "asyncAfter(deadline: .now() + 20)" in source
    assert 'send(\'restartCore\')' in source
    assert 'action == "restartCore"' in source
    assert 'action == "openDiagnosticLog"' in source
    assert "size > 5 * 1024 * 1024" in source
    assert 'appendingPathExtension("1")' in source
    assert "if self.core === process { self.core = nil }" in source


def test_native_shell_surfaces_the_current_core_denial_before_offering_logs():
    source = (Path(__file__).parents[1] / "packaging" / "macos" /
              "CrossAuditApp.swift").read_text()
    assert "launchLogOffset" in source
    assert "try handle.seek(toOffset: launchLogOffset)" in source
    assert 'value.hasPrefix("DENIED (")' in source
    assert 'value.range(of: "): ")' in source
    assert "showFailure(denial, offersDiagnosticLog: false)" in source


def test_native_shell_keeps_projects_running_after_the_window_closes():
    source = (Path(__file__).parents[1] / "packaging" / "macos" /
              "CrossAuditApp.swift").read_text()
    assert "applicationShouldTerminateAfterLastWindowClosed" in source
    assert "func windowShouldClose" in source
    assert "sender.orderOut(nil)" in source
    assert "return false" in source
    assert "NSStatusBar.system.statusItem" in source
    assert 'title: "Open CrossAudit"' in source
    assert 'title: "Running in background"' in source
    assert 'title: "Quit CrossAudit"' in source
    assert "if !flag { showMainWindow() }" in source
    assert "guard let self, !self.isTerminating" in source


def test_native_shell_routes_standard_edit_commands_to_the_focused_web_field():
    source = (Path(__file__).parents[1] / "packaging" / "macos" /
              "CrossAuditApp.swift").read_text()
    assert 'NSMenu(title: "Edit")' in source
    for title, selector, key in (
        ("Undo", 'Selector(("undo:"))', "z"),
        ("Redo", 'Selector(("redo:"))', "z"),
        ("Cut", "#selector(NSText.cut(_:))", "x"),
        ("Copy", "#selector(NSText.copy(_:))", "c"),
        ("Paste", "#selector(NSText.paste(_:))", "v"),
        ("Select All", "#selector(NSText.selectAll(_:))", "a"),
    ):
        assert f'"{title}"' in source
        assert selector in source
        assert f'keyEquivalent: "{key}"' in source
    assert "redo.keyEquivalentModifierMask = [.command, .shift]" in source


def test_app_project_creation_requires_both_selected_provider_keys(
        tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.delenv("CROSSAUDIT_OPENAI_KEY", raising=False)
    monkeypatch.delenv("CROSSAUDIT_ANTHROPIC_KEY", raising=False)

    with pytest.raises(ConfigDenial, match="Openai API key in Settings"):
        projects.create_project(tmp_path, app_payload(), lambda *_: None)


def test_app_project_config_binds_keys_to_vendor_not_role(tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setenv("CROSSAUDIT_OPENAI_KEY", "openai-test")
    monkeypatch.setenv("CROSSAUDIT_ANTHROPIC_KEY", "anthropic-test")
    draft = Draft("A product review", "review", [
        Rule("CA-OUT-001", "BLOCKER", "One file", "Exactly one file exists.")])
    monkeypatch.setattr(projects.wizard, "_distil", lambda *a, **kw: draft)

    result = projects.create_project(tmp_path, app_payload(), lambda *_: None)
    cfg = load(Path(result["root"]) / "crossaudit.yml")

    assert cfg.auditor.key_env == "CROSSAUDIT_OPENAI_KEY"
    assert cfg.generator_key_env == "CROSSAUDIT_ANTHROPIC_KEY"
    assert "CA-TASK-001" in (cfg.root / cfg.constitution).read_text()


def test_project_can_bind_gemini_and_deepseek_without_openai_routing(
        tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setenv("CROSSAUDIT_GOOGLE_KEY", "google-test")
    monkeypatch.setenv("CROSSAUDIT_DEEPSEEK_KEY", "deepseek-test")
    monkeypatch.setattr(projects.wizard, "_distil", lambda *a, **kw: Draft(
        "A review", "review", [Rule("CA-OUT-001", "BLOCKER", "One output",
                                        "Exactly one output exists.")]))

    result = projects.create_project(tmp_path, app_payload(
        auditor_vendor="google", auditor_model="gemini-3.6-flash",
        generator_vendor="deepseek", generator_model="deepseek-v4-flash"),
        lambda *_: None)
    cfg = load(Path(result["root"]) / "crossaudit.yml")

    assert cfg.auditor.provider == "google"
    assert cfg.auditor.key_env == "CROSSAUDIT_GOOGLE_KEY"
    assert cfg.auditor.base_url is None
    assert cfg.generator_provider == "deepseek"
    assert cfg.generator_key_env == "CROSSAUDIT_DEEPSEEK_KEY"
    assert cfg.generator_base_url is None


def test_project_persists_each_roles_selected_api_region(tmp_path, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    monkeypatch.setenv("CROSSAUDIT_MINIMAX_KEY", "minimax-test")
    monkeypatch.setenv("CROSSAUDIT_QWEN_KEY", "qwen-test")
    monkeypatch.setattr(projects.wizard, "_distil", lambda *a, **kw: Draft(
        "A review", "review", [Rule("CA-OUT-001", "BLOCKER", "One output",
                                    "Exactly one output exists.")]))
    result = projects.create_project(tmp_path, app_payload(
        auditor_vendor="minimax", auditor_model="MiniMax-M2.7",
        auditor_endpoint="global", generator_vendor="qwen",
        generator_model="qwen3.7-plus", generator_endpoint="singapore"),
        lambda *_: None)
    cfg = load(Path(result["root"]) / "crossaudit.yml")
    assert cfg.auditor.base_url == "https://api.minimax.io/v1"
    assert cfg.generator_base_url == (
        "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")


def test_frozen_app_identity_uses_embedded_build_digest(tmp_path, monkeypatch):
    digest = "a" * 64
    (tmp_path / "crossaudit-build.json").write_text(json.dumps({
        "code_digest_sha256": digest, "version": "4.0.0"}))
    monkeypatch.setattr(_selfid.sys, "frozen", True, raising=False)
    monkeypatch.setattr(_selfid.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert _selfid.install_mode() == "frozen-app"
    assert _selfid.code_digest() == digest
    assert "frozen-app" in _selfid.ADMISSIBLE_MODES


def test_frozen_auditor_uses_embedded_deterministic_layer_digest(
        tmp_path, monkeypatch):
    digest = "b" * 64
    (tmp_path / "crossaudit-build.json").write_text(json.dumps({
        "code_digest_sha256": "a" * 64, "dcl_source_sha256": digest,
        "version": "4.14.0"}))
    monkeypatch.setattr(auditor_run.sys, "frozen", True, raising=False)
    monkeypatch.setattr(auditor_run.sys, "_MEIPASS", str(tmp_path), raising=False)

    assert auditor_run.dcl_source_digest() == digest


def test_project_console_anchors_process_cwd_to_the_requested_project(
        tmp_path, monkeypatch):
    project = tmp_path / "project"
    project.mkdir()
    (project / "crossaudit.yml").write_text("fixture\n", encoding="utf-8")
    observed = {}
    # Register the variable with monkeypatch so project_console's direct
    # os.environ assignment is undone after this test.
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "")
    monkeypatch.setattr(app, "load_into_environment", lambda: None)

    def stop_at_load(_path):
        observed["cwd"] = Path.cwd()
        raise RuntimeError("stop after cwd assertion")

    monkeypatch.setattr(app, "load", stop_at_load)
    before = Path.cwd()
    try:
        with pytest.raises(RuntimeError, match="cwd assertion"):
            app.project_console(project, 0)
    finally:
        os.chdir(before)
    assert observed["cwd"] == project.resolve()
