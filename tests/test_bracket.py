from itertools import combinations

import pytest

from app.bracket import bracket_predictions

SEEDS = (8, 1, 7, 2, 6, 3, 5, 4)


def test_even_matchups_have_equal_title_chances():
    result = bracket_predictions(SEEDS, dict.fromkeys(combinations(sorted(SEEDS), 2), 0.5))
    assert [len(matches) for matches in result.rounds] == [4, 2, 1]
    assert result.rounds[0][0].team_a == 8
    assert result.rounds[0][0].team_b == 1
    assert result.probability == 1 / 128
    assert set(result.championship.values()) == {1 / 8}


def test_canonical_probabilities_apply_in_seed_order():
    result = bracket_predictions(SEEDS, dict.fromkeys(combinations(sorted(SEEDS), 2), 1.0))
    assert result.rounds[0][0].probability_a == 0.0
    assert [match.winner for match in result.rounds[0]] == [1, 2, 3, 4]
    assert result.winner == 1
    assert result.probability == result.championship[1] == 1.0


def test_most_probable_complete_bracket_can_include_an_upset():
    teams = tuple(range(1, 9))
    probabilities = dict.fromkeys(combinations(teams, 2), 1.0)
    probabilities[1, 2] = 0.6
    probabilities[1, 3] = 0.5
    result = bracket_predictions(teams, probabilities)
    # The favorite's 60% quarterfinal path splits into two 30% paths in the semifinal.
    # The other quarterfinal outcome has a single 40% path to the championship.
    assert result.rounds[0][0].winner == 2
    assert result.rounds[0][0].winner_probability == pytest.approx(0.4)
    assert result.winner == 2
    assert result.probability == pytest.approx(0.4)
    assert sum(result.championship.values()) == pytest.approx(1.0)
    assert result.championship[2] == pytest.approx(0.4)
    assert result.championship[1] == result.championship[3] == pytest.approx(0.3)


def test_duplicate_teams_and_missing_matchups_are_rejected():
    with pytest.raises(ValueError, match="eight distinct"):
        bracket_predictions((1, 1, 2, 3, 4, 5, 6, 7), {})
    with pytest.raises(ValueError, match="Missing or invalid win probability"):
        bracket_predictions(SEEDS, {})
