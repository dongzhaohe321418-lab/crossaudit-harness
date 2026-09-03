"""Tests for the statistics, against values that can be derived by hand.

There is no scipy here to lean on, so every expected number below is either enumerated
by hand in the comment above it or is a textbook value.
"""

from __future__ import annotations

import pytest

from stats import mean, rank_with_ties, stderr, stdev, wilcoxon_signed_rank, wilson_interval


# --------------------------------------------------------------------------------------
# ranking
# --------------------------------------------------------------------------------------


def test_rank_with_ties_is_one_based():
    assert rank_with_ties([5.0, 1.0, 3.0]) == [3.0, 1.0, 2.0]


def test_tied_values_share_the_average_rank():
    # values 1,1,3 -> the two 1s take ranks 1 and 2, so both get 1.5; the 3 gets 3
    assert rank_with_ties([1.0, 1.0, 3.0]) == [1.5, 1.5, 3.0]


def test_three_way_tie_averages_all_three_ranks():
    assert rank_with_ties([2.0, 2.0, 2.0]) == [2.0, 2.0, 2.0]


# --------------------------------------------------------------------------------------
# Wilcoxon -- hand-enumerated exact values
# --------------------------------------------------------------------------------------


def test_six_all_positive_differences_gives_two_over_sixty_four():
    """n=6, W=0. Only two of the 2^6 sign assignments give min(W+,W-) <= 0:
    all-positive and all-negative. So p = 2/64 = 0.03125."""
    result = wilcoxon_signed_rank([0.1, 0.2, 0.3, 0.4, 0.5, 0.6])
    assert result.n_used == 6
    assert result.statistic == 0.0
    assert result.w_plus == 21.0  # 1+2+3+4+5+6
    assert result.w_minus == 0.0
    assert result.p_value == pytest.approx(2 / 64)
    assert "exact" in result.method


def test_one_small_negative_among_six_gives_four_over_sixty_four():
    """|d| ranks 1..6 with the negative on rank 1. min(W+,W-) = 1.
    Assignments with min <= 1: W+ in {0, 1, 20, 21} -> 4 of 64 -> 0.0625."""
    result = wilcoxon_signed_rank([-0.05, 0.1, 0.15, 0.2, 0.25, 0.3])
    assert result.statistic == 1.0
    assert result.p_value == pytest.approx(4 / 64)


def test_five_all_positive_cannot_reach_significance():
    """n=5: the most extreme possible outcome is p = 2/32 = 0.0625 > 0.05.

    This is why the report refuses to call anything significant below n=6.
    """
    result = wilcoxon_signed_rank([0.1, 0.2, 0.3, 0.4, 0.5])
    assert result.p_value == pytest.approx(2 / 32)
    assert result.p_value > 0.05


def test_the_test_is_symmetric_under_negation():
    forward = wilcoxon_signed_rank([0.3, -0.1, 0.2, 0.5, -0.05, 0.4])
    backward = wilcoxon_signed_rank([-0.3, 0.1, -0.2, -0.5, 0.05, -0.4])
    assert forward.p_value == pytest.approx(backward.p_value)
    assert forward.statistic == backward.statistic
    assert forward.w_plus == backward.w_minus


def test_a_balanced_sample_is_nowhere_near_significant():
    result = wilcoxon_signed_rank([0.1, -0.1, 0.2, -0.2, 0.3, -0.3])
    assert result.p_value == pytest.approx(1.0)


def test_exact_ties_are_dropped_and_declared():
    result = wilcoxon_signed_rank([0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.0])
    assert result.n_pairs == 8
    assert result.n_used == 6
    assert "2 of 8 pairs were exact ties" in result.note
    assert result.p_value == pytest.approx(2 / 64)


def test_all_ties_is_not_a_result():
    result = wilcoxon_signed_rank([0.0, 0.0, 0.0])
    assert result.n_used == 0
    assert result.p_value == 1.0
    assert result.method == "none"
    assert "nothing to work with" in result.note


def test_more_extreme_data_gives_a_smaller_p_value():
    mixed = wilcoxon_signed_rank([0.3, -0.2, 0.4, -0.1, 0.5, 0.2, 0.1, -0.3])
    clean = wilcoxon_signed_rank([0.3, 0.2, 0.4, 0.1, 0.5, 0.2, 0.1, 0.3])
    assert clean.p_value < mixed.p_value


def test_large_samples_switch_to_the_normal_approximation_and_say_so():
    result = wilcoxon_signed_rank([0.1 * i for i in range(1, 26)])
    assert result.n_used == 25
    assert "normal approximation" in result.method
    assert result.p_value < 0.001


def test_p_value_never_exceeds_one():
    assert wilcoxon_signed_rank([0.1, -0.1]).p_value <= 1.0


# --------------------------------------------------------------------------------------
# Wilson interval -- textbook values
# --------------------------------------------------------------------------------------


def test_wilson_interval_matches_the_published_value_for_seven_of_ten():
    result = wilson_interval(7, 10)
    assert result.point == 0.7
    assert result.low == pytest.approx(0.3968, abs=1e-3)
    assert result.high == pytest.approx(0.8922, abs=1e-3)


def test_wilson_interval_stays_inside_zero_and_one_at_the_extremes():
    """The reason Wilson is used rather than Wald: Wald would run outside [0,1] here."""
    none_of_three = wilson_interval(0, 3)
    assert none_of_three.low == 0.0
    assert none_of_three.high < 1.0
    all_of_three = wilson_interval(3, 3)
    assert all_of_three.high == 1.0
    assert all_of_three.low > 0.0


def test_a_tiny_sample_has_a_uselessly_wide_interval_and_shows_it():
    """3/4 confirmed looks like 75%, but the interval covers almost everything."""
    result = wilson_interval(3, 4)
    assert result.point == 0.75
    assert result.high - result.low > 0.5


def test_the_interval_narrows_as_the_sample_grows():
    small = wilson_interval(7, 10)
    large = wilson_interval(70, 100)
    assert (large.high - large.low) < (small.high - small.low)


def test_no_observations_is_reported_as_such():
    result = wilson_interval(0, 0)
    assert result.total == 0
    assert result.describe() == "no observations"


def test_impossible_proportions_are_refused():
    with pytest.raises(ValueError):
        wilson_interval(5, 3)


def test_describe_carries_the_counts_not_just_the_rate():
    assert "(7/10)" in wilson_interval(7, 10).describe()


# --------------------------------------------------------------------------------------
# means
# --------------------------------------------------------------------------------------


def test_mean_and_spread():
    assert mean([1.0, 2.0, 3.0]) == 2.0
    assert stdev([2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]) == pytest.approx(2.13809, abs=1e-4)
    assert stderr([1.0, 2.0, 3.0]) == pytest.approx(stdev([1.0, 2.0, 3.0]) / (3 ** 0.5))


def test_a_single_observation_has_no_spread_rather_than_an_error():
    assert stdev([4.0]) == 0.0
    assert stderr([4.0]) == 0.0
    assert mean([]) == 0.0
