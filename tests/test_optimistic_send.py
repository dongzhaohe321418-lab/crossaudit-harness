"""Instant feedback on send — the composer echoes the message + a working
indicator the moment Enter is pressed (Codex-style), before routing and the
first model token return. Pure client-side; asserted on the PAGE contract."""
from crossaudit.console.page import PAGE


def test_page_has_the_optimistic_echo_and_working_indicator():
    assert "function optimisticTurn(" in PAGE
    assert "let optimisticSend" in PAGE
    # The working indicator is the thinking orb (64 px) in the turn body; the
    # dots it replaced are gone, CSS included.
    assert "orbMarkup(intakeOrbPhase(intake),64,intakeOrbLabel(intake),'turn-orb')" in PAGE
    assert "thinking-dots" not in PAGE
    # Set on submit, and cleared when the real state takes over / on clarify / error.
    assert "optimisticSend={text:rawText" in PAGE
    assert "optimisticSend = null" in PAGE            # renderConversation hand-off
    # Reduced motion lives in the wrapper: one still frame, no loop.
    assert "prefers-reduced-motion: reduce" in PAGE
