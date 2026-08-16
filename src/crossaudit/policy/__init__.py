"""Capability policy: scoped grants + a deterministic decision engine.

The runtime never hands the model system authority. A Generator (or Auditor)
proposal is checked against a short-lived, narrowly-scoped ``CapabilityToken``
by a deterministic ``decide`` that does not consult a model — permission comes
from CrossAudit, not from anything a model says. Absent evidence never counts
in favour (the admission posture reused here), so an unknown tool, an
out-of-scope path, a fresh host, or an expired grant is denied by default.
"""
from .tokens import CapabilityToken, TokenError
from .engine import Decision, decide

__all__ = ["CapabilityToken", "TokenError", "Decision", "decide"]
