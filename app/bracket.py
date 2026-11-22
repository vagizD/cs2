"""Exact advancement chances and a projected path for an eight-team bracket."""

from dataclasses import dataclass
from itertools import combinations

BRACKET_SIZE = 8
ROUND_NAMES = ("Quarterfinals", "Semifinals", "Final")


@dataclass(frozen=True)
class MatchPrediction:
    team_a: int
    team_b: int
    probability_a: float

    @property
    def winner(self) -> int:
        return self.team_a if self.probability_a >= 0.5 else self.team_b


@dataclass(frozen=True)
class BracketPrediction:
    rounds: tuple[tuple[MatchPrediction, ...], ...]
    advancement: dict[int, tuple[float, ...]]

    @property
    def champion(self) -> int:
        return max(self.advancement, key=lambda team: self.advancement[team][-1])


def bracket_predictions(
    teams: tuple[int, ...], pair_probabilities: dict[tuple[int, int], float]
) -> BracketPrediction:
    if len(teams) != BRACKET_SIZE or len(set(teams)) != BRACKET_SIZE:
        raise ValueError("Choose eight distinct teams.")
    for pair in combinations(sorted(teams), 2):
        probability = pair_probabilities.get(pair)
        if probability is None or not 0.0 <= probability <= 1.0:
            raise ValueError(f"Missing or invalid win probability for teams {pair}.")

    def probability_for(team: int, opponent: int) -> float:
        if team < opponent:
            return pair_probabilities[team, opponent]
        return 1.0 - pair_probabilities[opponent, team]

    projected_teams = list(teams)
    possible_teams = [{team: 1.0} for team in teams]
    rounds = []
    advancement = {team: [] for team in teams}
    for _ in ROUND_NAMES:
        matches = []
        next_round = []
        for index in range(0, len(projected_teams), 2):
            team_a, team_b = projected_teams[index:index + 2]
            matches.append(MatchPrediction(team_a, team_b, probability_for(team_a, team_b)))

            left, right = possible_teams[index:index + 2]
            winners = dict.fromkeys((*left, *right), 0.0)
            # Separate bracket halves depend on disjoint earlier matches.
            for team, team_chance in left.items():
                for opponent, opponent_chance in right.items():
                    meet = team_chance * opponent_chance
                    win = probability_for(team, opponent)
                    winners[team] += meet * win
                    winners[opponent] += meet * (1.0 - win)
            next_round.append(winners)
            for team, chance in winners.items():
                advancement[team].append(chance)

        rounds.append(tuple(matches))
        possible_teams = next_round
        projected_teams = [match.winner for match in matches]

    return BracketPrediction(
        tuple(rounds), {team: tuple(chances) for team, chances in advancement.items()}
    )
