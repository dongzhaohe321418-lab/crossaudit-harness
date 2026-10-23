"""The usage ledger records which surface a completion came through (TUI_FIRST.md §5).

Declared at the entry point (`main()` -> cli, `serve()` -> console / app), never
guessed; rows written where nothing was declared carry no `surface` key and
read as `unknown`. Every test here drives the real writer, the real summary,
or the real entry point; only provider transports are stubbed.

D10 mutations (each turns the named tests red):
  * drop `event["surface"] = row_surface` in `record_reply` -> every
    `..._carries_...` / `..._records_...` test;
  * write `_SURFACE or "cli"` instead of `_SURFACE` -> the
    `no_surface_key` test;
  * swap the precedence (`_SURFACE or surface`) -> the explicit-keyword test;
  * aggregate `by_surface` inside the month branch only -> the whole-ledger
    test (its old rows are two months back);
  * delete `usage.set_surface(...)` in `serve` -> both console/app tests (the
    row says `cli`, which `main()` declared first);
  * ignore `CROSSAUDIT_USAGE_SURFACE` in `main()` -> the environment test;
  * drop the `usage` key from `cmd_status`'s JSON -> the status test.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "harness"))

from readme_project import FakeVendors, init_project, with_keys  # noqa: E402

from crossaudit import usage  # noqa: E402
from crossaudit.errors import EXIT_OK  # noqa: E402
from crossaudit.providers.base import Reply  # noqa: E402

TASK = ["Create", "a", "small", "reproducible", "benchmark"]


def _reply(prompt_tokens: int = 10, completion_tokens: int = 5) -> Reply:
    return Reply(text="{}", request_id="rid", request_sha256="a" * 64,
                 response_sha256="b" * 64,
                 raw={"usage": {"prompt_tokens": prompt_tokens,
                                "completion_tokens": completion_tokens}})


def _write(cfg, **extra):
    return usage.record_reply(
        root=cfg.root, state_dir=cfg.state_dir, role="generator",
        phase="generation", vendor="openai", provider="openai_compat",
        model="gpt-5.6-luna", reply=_reply(), system="s", prompt="p", **extra)


def _lines(root: Path, state_dir: str = ".crossaudit") -> list[dict]:
    path = Path(root) / state_dir / usage.LEDGER_NAME
    return [json.loads(line) for line in path.read_text().splitlines()]


# ---------------------------------------------------------------- the writer
def test_a_row_written_after_set_surface_cli_carries_surface_cli(cfg):
    assert usage.set_surface("cli") == "cli"
    event = _write(cfg)
    assert event["surface"] == "cli"
    assert _lines(cfg.root)[-1]["surface"] == "cli"      # persisted, not just returned


def test_a_row_written_with_no_surface_declared_has_no_surface_key(cfg):
    assert usage.surface() is None
    event = _write(cfg)
    assert "surface" not in event
    assert "surface" not in _lines(cfg.root)[-1]


def test_an_explicit_surface_keyword_wins_over_the_declared_surface(cfg):
    usage.set_surface("cli")
    event = _write(cfg, surface="tui")
    assert event["surface"] == "tui"
    assert usage.surface() == "cli"                       # the declaration is untouched


def test_an_invalid_surface_raises_and_record_completion_swallows_it(cfg):
    for bad in ("web", "", "CLI", None, 3):
        with pytest.raises(ValueError):
            usage.set_surface(bad)                        # type: ignore[arg-type]
    assert usage.surface() is None                        # a refused name never sticks
    with pytest.raises(ValueError):
        _write(cfg, surface="web")
    returned = usage.record_completion(
        root=cfg.root, state_dir=cfg.state_dir, role="generator",
        phase="generation", vendor="openai", provider="openai_compat",
        model="gpt-5.6-luna", reply=_reply(), system="s", prompt="p",
        surface="web")
    assert returned is None
    assert not (cfg.root / cfg.state_dir / usage.LEDGER_NAME).exists()


# --------------------------------------------------------------- the summary
def test_by_surface_counts_calls_and_value_over_the_whole_ledger_old_rows_unknown(cfg):
    usage.set_surface("cli")
    a = _write(cfg)
    b = _write(cfg)
    c = _write(cfg, surface="console")
    path = cfg.root / cfg.state_dir / usage.LEDGER_NAME
    # Two rows from an older ledger, two months back: no `surface` field, and
    # outside the month bucket. One from a hypothetical newer writer.
    old_t = int((datetime.now() - timedelta(days=62)).timestamp() * 1000)
    old = {"v": 1, "t": old_t, "role": "auditor", "phase": "audit",
           "vendor": "openai", "provider": "openai_compat", "model": "m",
           "input": 7, "output": 3, "cache_write": 0, "cache_read": 0,
           "total": 10, "method": "reported", "api_value_usd": 0.25,
           "billing_kind": "api_value"}
    with path.open("a") as fh:
        fh.write(json.dumps(old) + "\n")
        fh.write(json.dumps({**old, "api_value_usd": None}) + "\n")
        fh.write(json.dumps({**old, "surface": "watch"}) + "\n")

    result = usage.summary(cfg)
    by = result["by_surface"]
    assert list(by) == ["cli", "tui", "console", "app", "unknown", "watch"]
    assert by["cli"]["calls"] == 2
    assert by["cli"]["api_value_usd"] == pytest.approx(
        a["api_value_usd"] + b["api_value_usd"])
    assert by["console"]["calls"] == 1
    assert by["console"]["api_value_usd"] == pytest.approx(c["api_value_usd"])
    assert by["tui"]["calls"] == by["app"]["calls"] == 0
    assert by["unknown"]["calls"] == 2
    assert by["unknown"]["api_value_usd"] == pytest.approx(0.25)
    assert by["unknown"]["unpriced_calls"] == 1
    assert by["watch"]["calls"] == 1
    # The month excludes the old rows; by_surface does not.
    assert result["month"]["calls"] == 3
    assert sum(v["calls"] for v in by.values()) == result["all"]["calls"] == 6
    # Same bucket shape as `roles`.
    assert set(by["cli"]) == set(usage._blank())


def test_by_surface_memo_is_invalidated_by_a_new_row(cfg):
    usage.set_surface("cli")
    _write(cfg)
    assert usage.summary(cfg)["by_surface"]["cli"]["calls"] == 1
    _write(cfg, surface="tui")
    assert usage.summary(cfg)["by_surface"]["tui"]["calls"] == 1


# ----------------------------------------------------------- the entry points
@pytest.fixture()
def project(tmp_path, monkeypatch, capsys):
    with_keys(monkeypatch)
    root = init_project(tmp_path, monkeypatch)
    capsys.readouterr()
    return root


def test_crossaudit_build_writes_rows_with_surface_cli(project, monkeypatch):
    from crossaudit.cli import main

    FakeVendors().install(monkeypatch)
    assert main.main(["build", *TASK]) == EXIT_OK
    rows = _lines(project)
    assert {row["role"] for row in rows} >= {"generator", "auditor"}
    assert all(row.get("surface") == "cli" for row in rows), rows


def test_main_honours_crossaudit_usage_surface_from_a_parent(project, monkeypatch):
    from crossaudit.cli import main

    monkeypatch.setenv(usage.SURFACE_ENV, "tui")
    FakeVendors().install(monkeypatch)
    assert main.main(["build", *TASK]) == EXIT_OK
    rows = _lines(project)
    assert rows and all(row.get("surface") == "tui" for row in rows), rows


def test_main_ignores_an_invalid_crossaudit_usage_surface(project, monkeypatch):
    from crossaudit.cli import main

    monkeypatch.setenv(usage.SURFACE_ENV, "watch")
    assert main.main(["--json", "status"]) == EXIT_OK
    assert usage.surface() == "cli"


def test_status_json_carries_usage_by_surface_and_the_human_view_does_not(
        project, monkeypatch, capsys):
    from crossaudit.cli import main

    FakeVendors().install(monkeypatch)
    assert main.main(["build", *TASK]) == EXIT_OK
    calls = len(_lines(project))
    capsys.readouterr()
    assert main.main(["--json", "status"]) == EXIT_OK
    doc = json.loads(capsys.readouterr().out)
    by = doc["usage"]["by_surface"]
    # Every `--json` document is emitted with sort_keys, so the JSON object's
    # key order is alphabetical; the in-process order is pinned above.
    assert set(by) == {"cli", "tui", "console", "app", "unknown"}
    assert by["cli"]["calls"] == calls and by["unknown"]["calls"] == 0
    assert "api_value_usd" in by["cli"]
    assert main.main(["status"]) == EXIT_OK
    human = capsys.readouterr().out
    assert "by_surface" not in human and "surface" not in human


# ------------------------------------------------- the console's own process
@pytest.fixture()
def served(cfg):
    """`serve()` in this process, after `main()` would already have said cli."""
    from crossaudit.console import serve

    started = []

    def start():
        usage.set_surface("cli")          # what `crossaudit console` declared first
        _url, httpd = serve(cfg, port=0)
        started.append(httpd)
        return httpd

    yield start
    for httpd in started:
        # Never served, so `shutdown()` would wait forever; close the socket.
        httpd.server_close()


def _say(cfg, monkeypatch):
    """Drive the console's real `say` through routing to the chat lane, with
    only the provider transport stubbed (the same stubs test_billing uses)."""
    from crossaudit import router as router_mod
    from crossaudit.cli import talk as talk_mod
    from crossaudit.console import server as server_mod

    def route_addressed(text, *, complete, context=None, **_kw):
        complete(system="route", prompt=text)
        return router_mod.Routing(utterance=text, lane="chat", confidence=0.99,
                                  reasoning="conversational", restated=text, t=1,
                                  chat_id="a1b2c3d4e5f60718")

    monkeypatch.setattr(router_mod, "route_addressed", route_addressed)
    monkeypatch.setattr("crossaudit.providers.resilience.complete",
                        lambda *a, **k: _reply(40, 10))
    monkeypatch.setattr(talk_mod, "_record_routing", lambda *a, **k: None)
    monkeypatch.setattr(server_mod, "setup_needed", lambda _cfg: None)
    server_mod.say(cfg, "what is 1 + 1?", chat_id="a1b2c3d4e5f60718")
    return _lines(cfg.root, cfg.state_dir)


def test_the_console_server_records_its_own_completions_as_console(
        cfg, served, monkeypatch):
    monkeypatch.delenv("CROSSAUDIT_APP_MODE", raising=False)
    served()
    assert usage.surface() == "console"
    rows = _say(cfg, monkeypatch)
    assert rows and {row["role"] for row in rows} >= {"router"}
    assert all(row.get("surface") == "console" for row in rows), rows


def test_app_mode_records_the_servers_completions_as_app(cfg, served, monkeypatch):
    monkeypatch.setenv("CROSSAUDIT_APP_MODE", "1")
    served()
    assert usage.surface() == "app"
    rows = _say(cfg, monkeypatch)
    assert rows and all(row.get("surface") == "app" for row in rows), rows


def test_a_build_thread_of_the_console_process_records_console(cfg, served,
                                                               monkeypatch):
    """`start_build` runs the loop on a thread of the server process
    (`RunCommandService.start(background=True)`), not in a child: the
    declaration is process-wide, so a worker thread inherits it."""
    monkeypatch.delenv("CROSSAUDIT_APP_MODE", raising=False)
    served()
    out = []
    worker = threading.Thread(target=lambda: out.append(_write(cfg)))
    worker.start()
    worker.join(5)
    assert out and out[0]["surface"] == "console"
