"""`AuthorizationStore` never loses a concurrent update (D169, F3).

Before D169 every write was load -> modify -> persist with no lock, through
a temp file named ``authorizations.json.tmp<pid>`` that every thread of the
process shared. 40 threads calling `add_tool` gave 24 FileNotFoundError and
kept 5 of 40 tools. The real race is a build thread approving a tool "for
this project" (humanapproval) while the settings UI toggles
``workspace_writes``; a lost REVOKE there is fail-open.

Mutations (D10), run by hand: removing the `with _LOCK:` from `_update`
turns the 40-thread, the set/set_list and the revoke-race tests red (the
race test reports a lost revoke or a lost grant, whichever write lost; three
runs gave both); restoring the pid-only temp name with the
lock in place turns the temp-name test red (the lock alone hides the shared
name inside one process, so that test pins the name directly).
"""
from __future__ import annotations

import threading
from types import SimpleNamespace

import pytest

from crossaudit.broker import approval
from crossaudit.broker.approval import (APPROVED_TOOLS, WORKSPACE_WRITES,
                                        AuthorizationStore)


@pytest.fixture()
def store(tmp_path):
    cfg = SimpleNamespace(root=tmp_path, state_dir=".crossaudit")
    return AuthorizationStore(cfg)  # type: ignore[arg-type]


def _run_together(targets) -> list[BaseException]:
    errors: list[BaseException] = []
    barrier = threading.Barrier(len(targets))

    def wrap(fn):
        def run():
            barrier.wait()
            try:
                fn()
            except BaseException as exc:  # noqa: BLE001 - collected for the assert
                errors.append(exc)
        return run

    threads = [threading.Thread(target=wrap(fn)) for fn in targets]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)
    assert not any(t.is_alive() for t in threads)
    return errors


def test_forty_threads_adding_tools_keep_all_forty(store):
    tools = [f"tool_{i}" for i in range(40)]
    errors = _run_together([lambda t=t: store.add_tool(t) for t in tools])

    assert errors == []
    assert sorted(store.load()[APPROVED_TOOLS]) == sorted(tools)
    assert all(store.authorized_tool(t) for t in tools)
    leftovers = [p.name for p in store.path.parent.iterdir() if p.name != store.path.name]
    assert leftovers == []


def test_a_revoke_racing_a_grant_of_another_key_is_never_lost(store):
    for i in range(300):
        store.set(WORKSPACE_WRITES, True)
        tool = f"tool_{i}"
        errors = _run_together([lambda: store.set(WORKSPACE_WRITES, False),
                                lambda t=tool: store.add_tool(t)])
        assert errors == []
        data = store.load()
        assert data[WORKSPACE_WRITES] is False, f"revoke lost at iteration {i}"
        assert tool in data[APPROVED_TOOLS], f"grant lost at iteration {i}"


def test_set_and_set_list_from_many_threads_lose_nothing(store):
    keys = [f"key_{i}" for i in range(20)]
    lists = [f"list_{i}" for i in range(20)]
    targets = [lambda k=k: store.set(k, True) for k in keys]
    targets += [lambda k=k: store.set_list(k, [k, "x"]) for k in lists]
    errors = _run_together(targets)

    assert errors == []
    data = store.load()
    assert all(data[k] is True for k in keys)
    assert all(data[k] == [k, "x"] for k in lists)


def test_temp_names_do_not_collide_across_threads(store, monkeypatch):
    seen: list[str] = []
    real_replace = approval.os.replace

    def record(src, dst):
        seen.append(str(src))
        return real_replace(src, dst)

    monkeypatch.setattr(approval.os, "replace", record)
    errors = _run_together([lambda i=i: store.set(f"k{i}", True) for i in range(16)])

    assert errors == []
    assert len(seen) == 16 and len(set(seen)) == 16
    for name in seen:
        assert name.startswith(str(store.path) + ".tmp")
        assert name != str(store.path) + f".tmp{approval.os.getpid()}"
