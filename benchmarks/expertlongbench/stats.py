"""The statistics the study reports, kept small, pure and testable.

No scipy: the package's only dependencies are PyYAML, certifi and the document libraries,
and a benchmark is not a reason to add a numerical stack. Everything here is exact for the
sample sizes this study can afford.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class WilcoxonResult:
    """Two-sided Wilcoxon signed-rank test on paired differences."""

    n_pairs: int
    #: pairs left after dropping exact ties, which the test cannot use
    n_used: int
    w_plus: float
    w_minus: float
    statistic: float
    p_value: float
    method: str
    note: str = ""


def rank_with_ties(values: Sequence[float]) -> list[float]:
    """Average ranks, 1-based."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    position = 0
    while position < len(order):
        end = position
        while end + 1 < len(order) and values[order[end + 1]] == values[order[position]]:
            end += 1
        average = (position + end) / 2 + 1
        for index in range(position, end + 1):
            ranks[order[index]] = average
        position = end + 1
    return ranks


def wilcoxon_signed_rank(differences: Sequence[float]) -> WilcoxonResult:
    """Two-sided test of the null that the paired differences are centred on zero.

    Exact by enumeration for n <= 20 -- which is the only regime a study at this cost can
    reach, and where the normal approximation is not trustworthy. Above that, a normal
    approximation with a continuity correction, and the method is named in the output so a
    reader knows which was used.

    Exact ties (a difference of exactly zero) are dropped, following Wilcoxon's original
    treatment; the count of dropped pairs is reported, because dropping many of them makes
    the surviving p-value describe a smaller study than the one that was run.
    """
    non_zero = [d for d in differences if d != 0]
    n_used = len(non_zero)
    if n_used == 0:
        return WilcoxonResult(
            n_pairs=len(differences),
            n_used=0,
            w_plus=0.0,
            w_minus=0.0,
            statistic=0.0,
            p_value=1.0,
            method="none",
            note="every pair was an exact tie; the test has nothing to work with",
        )

    ranks = rank_with_ties([abs(d) for d in non_zero])
    w_plus = sum(r for d, r in zip(non_zero, ranks) if d > 0)
    w_minus = sum(r for d, r in zip(non_zero, ranks) if d < 0)
    statistic = min(w_plus, w_minus)

    if n_used <= 20:
        # Enumerate every assignment of signs to the observed |differences|.
        total = 0
        at_least_as_extreme = 0
        for signs in itertools.product((1, -1), repeat=n_used):
            plus = sum(r for s, r in zip(signs, ranks) if s > 0)
            minus = sum(ranks) - plus
            total += 1
            if min(plus, minus) <= statistic:
                at_least_as_extreme += 1
        p_value = at_least_as_extreme / total
        method = f"exact (enumerated 2^{n_used})"
    else:
        mean = n_used * (n_used + 1) / 4
        variance = n_used * (n_used + 1) * (2 * n_used + 1) / 24
        z = (abs(statistic - mean) - 0.5) / math.sqrt(variance)
        p_value = 2 * (1 - _normal_cdf(z))
        method = "normal approximation with continuity correction"

    note = ""
    dropped = len(differences) - n_used
    if dropped:
        note = f"{dropped} of {len(differences)} pairs were exact ties and were dropped"

    return WilcoxonResult(
        n_pairs=len(differences),
        n_used=n_used,
        w_plus=w_plus,
        w_minus=w_minus,
        statistic=statistic,
        p_value=min(1.0, p_value),
        method=method,
        note=note,
    )


def _normal_cdf(z: float) -> float:
    return 0.5 * (1 + math.erf(z / math.sqrt(2)))


@dataclass(frozen=True)
class Proportion:
    """A rate with a Wilson score interval."""

    successes: int
    total: int
    point: float
    low: float
    high: float
    confidence: float = 0.95

    def describe(self) -> str:
        if self.total == 0:
            return "no observations"
        return (
            f"{self.point * 100:.1f}% ({self.successes}/{self.total}), "
            f"95% CI [{self.low * 100:.1f}%, {self.high * 100:.1f}%]"
        )


def wilson_interval(successes: int, total: int, z: float = 1.959963984540054) -> Proportion:
    """Wilson score interval.

    Chosen over the normal (Wald) interval because this study's rates rest on a handful of
    findings, where Wald produces intervals that run past 0 or 1 and understates the width
    exactly when it matters most.
    """
    if total <= 0:
        return Proportion(successes, 0, 0.0, 0.0, 1.0)
    if successes < 0 or successes > total:
        raise ValueError(f"{successes} successes out of {total} is not a proportion")

    p = successes / total
    denominator = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denominator
    spread = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denominator
    # At the extremes the bound is exactly 0 or 1 analytically; snap it, because floating
    # point leaves a residue there (5.6e-17 instead of 0) and a "0.0000001% lower bound"
    # in a report reads as a real number rather than as arithmetic noise.
    low = 0.0 if successes == 0 else max(0.0, centre - spread)
    high = 1.0 if successes == total else min(1.0, centre + spread)
    return Proportion(successes=successes, total=total, point=p, low=low, high=high)


def mean(values: Sequence[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def stdev(values: Sequence[float]) -> float:
    """Sample standard deviation; 0.0 for fewer than two values."""
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1))


def stderr(values: Sequence[float]) -> float:
    return stdev(values) / math.sqrt(len(values)) if len(values) >= 2 else 0.0
