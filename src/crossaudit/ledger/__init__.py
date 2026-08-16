"""Append-only, hash-chained evidence ledger for the Agentic Runtime.

Phase 1 foundation (see docs/AGENTIC_RUNTIME_PHASE0.md). Every governed action
— a tool proposal, a policy decision, an execution result, a human approval —
is recorded here as a self-verifying entry whose digest chains to the one
before it, so an Auditor can review *what actually ran* and a verifier can
re-derive the whole chain offline and refuse on the first tampered byte.

This is distinct from the audit-cycle ``receipt`` (which binds one audit to one
commit): the ledger is a generic, cross-entry evidence chain. It reuses the
receipt's canonical/digest hashing so audit and verify stay byte-identical.
"""
from .chain import (
    LEDGER_SCHEMA,
    EvidenceLedger,
    LedgerError,
    VerifyReport,
)

__all__ = ["LEDGER_SCHEMA", "EvidenceLedger", "LedgerError", "VerifyReport"]
