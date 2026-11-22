from itertools import combinations

import pytest

from app.bracket import bracket_predictions

SEEDS = (8, 1, 7, 2, 6, 3, 5, 4)


def test_even_matchups_have_equal_advancement_chances():
    result = bracket_predictions(SEEDS, dict.fromkeys(combinations(sorted(SEEDS), 2), 0.5))
    assert [len(matches) for matches in result.rounds] == [4, 2, 1]
    assert result.rounds[0][0].team_a == 8
    assert result.rounds[0][0].team_b == 1
    assert all(chances == (0.5, 0.25, 0.125) for chances in result.advancement.values())


def test_canonical_probabilities_apply_in_seed_order():
    result = bracket_predictions(SEEDS, dict.fromkeys(combinations(sorted(SEEDS), 2), 1.0))
    assert result.rounds[0][0].probability_a == 0.0
    assert [match.winner for match in result.rounds[0]] == [1, 2, 3, 4]
    assert result.rounds[-1][0].winner == result.champion == 1
    assert result.advancement[1] == (1.0, 1.0, 1.0)


def test_favorite_wins_three_rounds_and_each_stage_totals_are_correct():
    probabilities = {
        pair: 0.6 if 1 in pair else 0.5 for pair in combinations(sorted(SEEDS), 2)
    }
    result = bracket_predictions(SEEDS, probabilities)
    assert result.champion == 1
    assert result.advancement[1] == pytest.approx((0.6, 0.6**2, 0.6**3))
    assert [sum(chances) for chances in zip(*result.advancement.values())] == pytest.approx(
        (4, 2, 1)
    )


def test_duplicate_teams_and_missing_matchups_are_rejected():
    with pytest.raises(ValueError, match="eight distinct"):
        bracket_predictions((1, 1, 2, 3, 4, 5, 6, 7), {})
    with pytest.raises(ValueError, match="Missing or invalid win probability"):
        bracket_predictions(SEEDS, {})
