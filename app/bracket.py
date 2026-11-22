"""Exact odds for an eight-team single-elimination bracket."""

from dataclasses import dataclass
from itertools import combinations, product

BRACKET_SIZE = 8
ROUND_NAMES = ("Quarterfinals", "Semifinals", "Final")


@dataclass(frozen=True)
class MatchPrediction:
    team_a: int
    team_b: int
    probability_a: float
    winner: int

    @property
    def winner_probability(self) -> float:
        return self.probability_a if self.winner == self.team_a else 1.0 - self.probability_a


@dataclass(frozen=True)
class BracketPrediction:
    rounds: tuple[tuple[MatchPrediction, ...], ...]
    probability: float
    championship: dict[int, float]

    @property
    def winner(self) -> int:
        return self.rounds[-1][0].winner


def bracket_predictions(
    teams: tuple[int, ...], pair_probabilities: dict[tuple[int, int], float]
) -> BracketPrediction:
    if len(teams) != BRACKET_SIZE or len(set(teams)) != BRACKET_SIZE:
        raise ValueError("Choose eight distinct teams.")
    for pair in combinations(sorted(teams), 2):
        probability = pair_probabilities.get(pair)
        if probability is None or not 0.0 <= probability <= 1.0:
            raise ValueError(f"Missing or invalid win probability for teams {pair}.")

    championship = dict.fromkeys(teams, 0.0)
    best_probability = -1.0
    best_rounds = ()
    # Seven binary results give 128 complete brackets. Later matchups depend on earlier results.
    for outcomes in product((0, 1), repeat=BRACKET_SIZE - 1):
        choices = iter(outcomes)
        remaining = teams
        probability = 1.0
        rounds = []
        for _ in ROUND_NAMES:
            matches = []
            for team_a, team_b in zip(remaining[::2], remaining[1::2], strict=True):
                low, high = sorted((team_a, team_b))
                chance = pair_probabilities[low, high]
                probability_a = chance if team_a == low else 1.0 - chance
                winner = (team_a, team_b)[next(choices)]
                match = MatchPrediction(team_a, team_b, probability_a, winner)
                probability *= match.winner_probability
                matches.append(match)
            rounds.append(tuple(matches))
            remaining = tuple(match.winner for match in matches)

        championship[remaining[0]] += probability
        if probability > best_probability:
            best_probability = probability
            best_rounds = tuple(rounds)

    return BracketPrediction(best_rounds, best_probability, championship)
