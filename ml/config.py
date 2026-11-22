import argparse
import math
import os
from pathlib import Path
from typing import Annotated, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, model_validator

Version = Annotated[str, Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}$")]
DEFAULT_CONFIG = Path("config.yaml")


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class Project(Settings):
    name: str
    random_seed: int = Field(ge=0, le=2**32 - 1)


class Data(Settings):
    local_db_path: Path
    gcs_db_path: Path
    gcs_uri: str | None
    snapshot_version: Version
    lookback_days: tuple[PositiveInt, PositiveInt]

    @model_validator(mode="after")
    def check_lookbacks(self):
        if self.lookback_days[0] >= self.lookback_days[1]:
            raise ValueError("lookback_days must be strictly increasing")
        return self


class Split(Settings):
    train_fraction: float = Field(gt=0, lt=1)
    val_fraction: float = Field(gt=0, lt=1)
    test_fraction: float = Field(gt=0, lt=1)

    @model_validator(mode="after")
    def check_total(self):
        if not math.isclose(self.train_fraction + self.val_fraction + self.test_fraction, 1):
            raise ValueError("Split fractions must sum to 1")
        return self


class Model(Settings):
    kind: Literal["logistic_regression"]
    max_iter: PositiveInt
    c: float = Field(gt=0, allow_inf_nan=False)


class Tracking(Settings):
    experiment_name: str
    tracking_uri: str


class API(Settings):
    minimum_matches: PositiveInt
    team_limit: int = Field(ge=2, le=500)


class Config(Settings):
    project: Project
    data: Data
    split: Split
    model: Model
    mlflow: Tracking
    api: API
    artifacts_dir: Path

    @property
    def model_path(self) -> Path:
        return Path(os.environ.get("MODEL_PATH", self.artifacts_dir / "model"))


def load_config(path: Path = DEFAULT_CONFIG) -> Config:
    with path.open(encoding="utf-8") as handle:
        config = yaml.safe_load(handle)
    overrides = {
        "GCS_URI": ("data", "gcs_uri"),
        "SNAPSHOT_VERSION": ("data", "snapshot_version"),
        "MLFLOW_TRACKING_URI": ("mlflow", "tracking_uri"),
    }
    for environment, (section, key) in overrides.items():
        if environment in os.environ:
            config[section][key] = os.environ[environment]
    if "ARTIFACTS_DIR" in os.environ:
        config["artifacts_dir"] = os.environ["ARTIFACTS_DIR"]
    return Config.model_validate(config)


def database_path(config: Config, source: Literal["local", "gcs"] = "local") -> Path:
    default = config.data.gcs_db_path if source == "gcs" else config.data.local_db_path
    return Path(os.environ.get("DATABASE_PATH", default))


def config_parser(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    return parser
