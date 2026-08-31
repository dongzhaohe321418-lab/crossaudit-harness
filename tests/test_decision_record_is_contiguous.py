"""The decision record lost D71-D73 in a conflict resolution and no test noticed.

D72 was "Shown 0 of 7" -- the audit that found I had been counting defect
closures as deliverable evidence. Losing it silently is worse than never
writing it: the record then reads as if the finding was never made.

Nothing in the suite covers docs/, so the loss surfaced only because an
engineer hit the same conflict and said the numbers were missing. This is the
cheapest possible guard for the failure it actually had: the headings are
numbered, so a gap is arithmetic.

MUTATION (D64 -- a guard is specified with its mutation): delete any "## Dnn"
section from docs/DECISIONS.md and this reddens naming that exact number.
Verified by deleting D72 and observing `missing decisions: [72]`.
"""

import re
from pathlib import Path

DECISIONS = Path(__file__).resolve().parents[1] / "docs" / "DECISIONS.md"


def test_decision_numbers_have_no_gaps():
    nums = sorted(int(n) for n in re.findall(r"^## D(\d+)\b", DECISIONS.read_text(), re.M))
    assert nums, "no decisions found -- the record moved or the heading style changed"
    missing = sorted(set(range(nums[0], nums[-1] + 1)) - set(nums))
    assert not missing, (
        f"missing decisions: {missing}. A gap means entries were dropped, most "
        f"likely by a conflict resolution that kept one side of docs/DECISIONS.md."
    )


def test_decision_numbers_are_unique():
    nums = re.findall(r"^## D(\d+)\b", DECISIONS.read_text(), re.M)
    dupes = sorted({n for n in nums if nums.count(n) > 1})
    assert not dupes, f"duplicate decision numbers: {dupes}. Two entries claim one number."
