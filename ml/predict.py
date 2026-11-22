"""Run the exported model on canonical matchup contexts."""

from ml.config import Config, database_path
from ml.features import available_teams, feature_matrix, inference_examples
from ml.model_artifact import load_model
from ml.snapshot import open_snapshot


class TeamSelectionError(ValueError):
    pass


class Predictor:
    def __init__(self, config: Config):
        self.pipeline, self.metadata = load_model(config.model_path)
        if config.data.lookback_days != self.metadata.lookback_days:
            raise ValueError("Configured lookbacks differ from the fitted model.")

        self.path = database_path(config)
        self.snapshot = open_snapshot(self.path, config.data.snapshot_version)
        trained_on = self.metadata.training_snapshot
        if (self.snapshot.snapshot_version == trained_on.snapshot_version
                and self.snapshot.sha256 != trained_on.sha256):
            raise ValueError("Serving snapshot checksum differs for the same snapshot version.")

        self.as_of = self.snapshot.inference_cutoff
        self.as_of_sql = self.as_of.strftime("%Y-%m-%d %H:%M:%S")
        self.teams = available_teams(
            self.path, self.as_of_sql, self.metadata.lookback_days[0],
            config.api.minimum_matches, config.api.team_limit,
        )
        if len(self.teams) < 2:
            raise ValueError("The snapshot has fewer than two eligible teams.")
        self.team_ids = frozenset(team["team_id"] for team in self.teams)
        self.predict(self.teams[0]["team_id"], self.teams[1]["team_id"])

    def predict(self, team_a: int, team_b: int) -> tuple[float, float]:
        if team_a == team_b:
            raise TeamSelectionError("Choose two distinct team IDs.")
        unknown = sorted({team_a, team_b} - self.team_ids)
        if unknown:
            raise TeamSelectionError(f"Teams unavailable for prediction: {unknown}. Use GET /teams.")

        examples = inference_examples(
            self.path, [(team_a, team_b)], self.as_of_sql, self.metadata.lookback_days
        )
        probability = float(self.pipeline.predict_proba(feature_matrix(examples))[0, 1])
        if not 0.0 <= probability <= 1.0:
            raise ValueError("The model returned an invalid probability.")
        canonical = (probability, 1.0 - probability)
        return canonical if team_a < team_b else canonical[::-1]
