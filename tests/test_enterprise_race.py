"""Race / concurrency red-team: concurrency cannot fork the chain or
double-grant an approval.

Two components carry hard concurrency invariants that an attacker (or a mere
scheduling accident) could try to break:

* The **EvidenceLedger** serialises every append behind an ``O_EXCL`` lock.
  If two writers ever read the same head and both wrote, the chain would
  *fork*: a duplicated ``seq``/``prev`` that ``verify()`` must reject. We hammer
  ONE ledger with N threads x K appends and assert the survivors are a single,
  contiguous, uniquely-digested chain.

* The **ApprovalInbox** delivers a human decision to a blocked worker through a
  single ``threading.Condition``. A decision must be *consumed exactly once*:
  it may not be replayed to a second waiter, cross between two different runs,
  or let ``grant_run`` register the same grant twice. We race resolvers against
  waiters and assert single-delivery.

All threads are bounded (<= 8) and time-bounded (sub-second waits); nothing
touches the network or spawns a real build.
"""
from __future__ import annotations

import threading

import pytest

from crossaudit.broker.humanapproval import (
    DENY, ONCE, PROJECT, RUN, ApprovalInbox, PendingApproval)
from crossaudit.ledger import EvidenceLedger


# ===========================================================================
# Attack (a) — concurrent appends must not FORK the evidence chain.
# ===========================================================================
def test_concurrent_ledger_appends_never_fork_the_chain(tmp_path):
    """N threads each append K entries to ONE ledger. The O_EXCL lock must
    serialise them into a single chain: verify() ok, count == N*K, seqs are a
    contiguous 0..N*K-1, and every digest is unique. A fork (two writers taking
    the same head) would duplicate a seq/prev and verify() would reject it."""
    led = EvidenceLedger(tmp_path / "evidence.jsonl")
    writers, per = 8, 15
    total = writers * per

    errors: list[BaseException] = []
    start = threading.Barrier(writers)

    def work(w: int) -> None:
        try:
            start.wait()  # release all writers at once for maximum contention
            for i in range(per):
                led.append("note", run_id=f"w{w}",
                           payload={"w": w, "i": i}, ts=f"{w}-{i}")
        except BaseException as exc:  # pragma: no cover - surfaced below
            errors.append(exc)

    threads = [threading.Thread(target=work, args=(w,)) for w in range(writers)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30.0)
    assert not any(t.is_alive() for t in threads), "a writer thread hung"
    assert not errors, f"append raised under contention: {errors!r}"

    report = led.verify()
    assert report.ok, report.error
    assert report.count == total

    entries = led.entries()
    assert len(entries) == total
    # Contiguous 0..total-1 — no gap (a lost append) and no duplicate (a fork).
    assert sorted(e["seq"] for e in entries) == list(range(total))
    # Every recorded digest is distinct: no two entries collapsed to one head.
    digests = [e["digest"] for e in entries]
    assert len(set(digests)) == total
    # And the links actually chain: genesis has empty prev, each prev == prior.
    assert entries[0]["prev"] == ""
    for prior, cur in zip(entries, entries[1:]):
        assert cur["prev"] == prior["digest"]
    assert led.head() == entries[-1]["digest"]


def test_two_ledger_instances_on_one_path_still_chain(tmp_path):
    """Two independent EvidenceLedger objects over the SAME file (as separate
    threads would each construct) share the on-disk O_EXCL lock. Interleaved
    appends from both must still produce one valid, contiguous chain — neither
    instance's head cache is allowed to fork the file."""
    path = tmp_path / "evidence.jsonl"
    a = EvidenceLedger(path)
    b = EvidenceLedger(path)
    per = 12
    errors: list[BaseException] = []
    start = threading.Barrier(2)

    def work(led: EvidenceLedger, tag: str) -> None:
        try:
            start.wait()
            for i in range(per):
                led.append("note", run_id=tag, payload={"i": i}, ts=f"{tag}-{i}")
        except BaseException as exc:  # pragma: no cover
            errors.append(exc)

    ta = threading.Thread(target=work, args=(a, "a"))
    tb = threading.Thread(target=work, args=(b, "b"))
    ta.start(); tb.start()
    ta.join(timeout=30.0); tb.join(timeout=30.0)
    assert not errors, f"append raised: {errors!r}"

    # A fresh reader trusts nothing it did not recompute.
    fresh = EvidenceLedger(path)
    report = fresh.verify()
    assert report.ok, report.error
    assert report.count == 2 * per
    assert sorted(e["seq"] for e in fresh.entries()) == list(range(2 * per))


# ===========================================================================
# Attack (b) — an approval decision is consumed EXACTLY once.
# ===========================================================================
def test_resolve_race_delivers_one_decision_then_returns_false(tmp_path):
    """Many threads race resolve() against a single waiter. The waiter returns
    exactly one decision; once it has consumed the pending action, a further
    resolve for that run finds nothing pending and returns False."""
    inbox = ApprovalInbox()
    inbox.open(PendingApproval("r", "run_check", 3, False))

    decision_box: dict[str, object] = {}
    results: list[bool] = []
    results_lock = threading.Lock()
    n_resolvers = 7
    start = threading.Barrier(n_resolvers + 1)

    def waiter() -> None:
        start.wait()
        decision_box["d"] = inbox.wait("r", timeout=4.0, poll=0.01)

    def resolver() -> None:
        start.wait()
        ok = inbox.resolve("r", RUN)
        with results_lock:
            results.append(ok)

    wt = threading.Thread(target=waiter)
    rts = [threading.Thread(target=resolver) for _ in range(n_resolvers)]
    wt.start()
    for t in rts:
        t.start()
    wt.join(timeout=10.0)
    for t in rts:
        t.join(timeout=10.0)

    assert not wt.is_alive(), "the waiter never woke"
    decided = decision_box["d"]
    assert decided is not None and decided.scope == RUN   # exactly one decision
    # At least one resolve was delivered while the action was still pending.
    assert any(results)
    # After the waiter consumed it, the pending card is gone...
    assert inbox.pending("r") is None
    # ...and a *fresh* resolve cannot re-deliver a stale grant.
    assert inbox.resolve("r", RUN) is False


def test_single_resolve_reaches_only_one_of_two_same_run_waiters(tmp_path):
    """The core anti-double-grant guarantee: one pending action + one resolve
    must wake exactly ONE waiter with the real decision. A second waiter racing
    the same run cannot also consume that single grant — it denies by timeout."""
    inbox = ApprovalInbox()
    inbox.open(PendingApproval("r", "run_check", 3, False))

    scopes: list[str] = []
    scopes_lock = threading.Lock()
    start = threading.Barrier(3)  # two waiters + the resolver

    def waiter() -> None:
        start.wait()
        d = inbox.wait("r", timeout=1.0, poll=0.01)
        with scopes_lock:
            scopes.append(d.scope)

    def resolver() -> None:
        start.wait()
        inbox.resolve("r", RUN)

    w1 = threading.Thread(target=waiter)
    w2 = threading.Thread(target=waiter)
    rt = threading.Thread(target=resolver)
    for t in (w1, w2, rt):
        t.start()
    for t in (w1, w2, rt):
        t.join(timeout=10.0)

    assert sorted(scopes) == sorted([RUN, DENY]), scopes
    # Exactly one real grant, exactly one deny-by-default. Never RUN twice.
    assert scopes.count(RUN) == 1
    assert scopes.count(DENY) == 1


def test_consumed_grant_cannot_be_replayed_to_a_later_waiter(tmp_path):
    """A grant is single-use across time, not just across a race. After one
    waiter consumes the decision, a second wait() for the same run — with no new
    resolve — must deny by timeout, never re-see the earlier grant."""
    inbox = ApprovalInbox()
    inbox.open(PendingApproval("r", "run_check", 3, False))
    assert inbox.resolve("r", RUN) is True
    first = inbox.wait("r", timeout=1.0, poll=0.01)
    assert first.scope == RUN
    # No fresh resolve, no pending — the earlier decision is fully consumed.
    assert inbox.pending("r") is None
    second = inbox.wait("r", timeout=0.1, poll=0.02)
    assert second.scope == DENY


def test_grant_run_is_idempotent_under_concurrency(tmp_path):
    """grant_run for the SAME (run, tool) from many threads must collapse to a
    single grant — the run-grant set cannot be double-registered by a race."""
    inbox = ApprovalInbox()
    n = 8
    start = threading.Barrier(n)

    def grant() -> None:
        start.wait()
        inbox.grant_run("r", "run_check")

    threads = [threading.Thread(target=grant) for _ in range(n)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)

    assert inbox.run_granted("r", "run_check")
    # Two grants == one grant: the set holds exactly the single (run, tool) key.
    assert inbox._run_grants == {("r", "run_check")}


# ===========================================================================
# Attack (c) — two waiters for different runs must not cross decisions.
# ===========================================================================
def test_two_waiters_for_different_runs_do_not_cross_decisions(tmp_path):
    """Two runs each pending, each with its own waiter, resolved concurrently
    with DISTINCT scopes. Each waiter must receive its own run's decision — the
    shared Condition must not deliver run A's grant to run B's waiter."""
    inbox = ApprovalInbox()
    inbox.open(PendingApproval("ra", "run_check", 3, False))
    inbox.open(PendingApproval("rb", "git_commit", 3, False))

    got: dict[str, str] = {}
    got_lock = threading.Lock()
    # 2 waiters + 2 resolvers all released together.
    start = threading.Barrier(4)

    def waiter(run_id: str) -> None:
        start.wait()
        d = inbox.wait(run_id, timeout=4.0, poll=0.01)
        with got_lock:
            got[run_id] = d.scope

    def resolver(run_id: str, scope: str) -> None:
        start.wait()
        # Retry briefly in case the waiter has not yet re-registered pending.
        for _ in range(200):
            if inbox.resolve(run_id, scope):
                return
        raise AssertionError(f"could not resolve {run_id}")

    threads = [
        threading.Thread(target=waiter, args=("ra",)),
        threading.Thread(target=waiter, args=("rb",)),
        threading.Thread(target=resolver, args=("ra", ONCE)),
        threading.Thread(target=resolver, args=("rb", PROJECT)),
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10.0)
    assert not any(t.is_alive() for t in threads), "a thread hung"

    # No crossing: each run got exactly the scope resolved for IT.
    assert got == {"ra": ONCE, "rb": PROJECT}
