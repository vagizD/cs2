from typing import Annotated

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

TeamId = Annotated[int, Field(strict=True, gt=0, le=2**63 - 1)]
Probability = Annotated[float, Field(ge=0, le=1)]


class Team(BaseModel):
    team_id: TeamId
    name: str


class PredictionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    team_a_id: TeamId
    team_b_id: TeamId

    @model_validator(mode="after")
    def distinct_teams(self):
        if self.team_a_id == self.team_b_id:
            raise ValueError("Choose two distinct team IDs.")
        return self


class PredictionResponse(BaseModel):
    team_a_id: TeamId
    team_b_id: TeamId
    team_a_win_probability: Probability
    team_b_win_probability: Probability
    as_of_utc: AwareDatetime
    model_version: str
    data_snapshot_version: str


class Health(BaseModel):
    ready: bool
    model_version: str | None = None
    data_snapshot_version: str | None = None
    data_snapshot_sha256: str | None = None
    training_snapshot_version: str | None = None
    as_of_utc: AwareDatetime | None = None
    detail: str | None = None
