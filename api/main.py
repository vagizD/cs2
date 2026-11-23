import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, Response

from api.schemas import Health, PredictionRequest, PredictionResponse, Team
from ml.config import DEFAULT_CONFIG, Config, load_config
from ml.predict import Predictor, TeamSelectionError

logger = logging.getLogger(__name__)
UNAVAILABLE = "Prediction service is not ready. Check model and snapshot configuration."


def get_predictor(request: Request) -> Predictor:
    predictor = request.app.state.predictor
    if predictor is None:
        raise HTTPException(status_code=503, detail=UNAVAILABLE)
    return predictor


def create_app(config: Config | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.predictor = None
        try:
            settings = config or load_config(Path(os.environ.get("CONFIG_PATH", DEFAULT_CONFIG)))
            app.state.predictor = Predictor(settings)
        except Exception:
            logger.exception("Could not initialize model and snapshot.")
        yield

    application = FastAPI(title="CS2 Match Predictor", lifespan=lifespan)
    application.state.predictor = None

    @application.get("/health", response_model_exclude_none=True)
    def health(request: Request, response: Response) -> Health:
        predictor = request.app.state.predictor
        if predictor is None:
            response.status_code = 503
            return Health(ready=False, detail=UNAVAILABLE)
        return Health(
            ready=True,
            model_version=predictor.metadata.model_version,
            data_snapshot_version=predictor.snapshot.snapshot_version,
            data_snapshot_sha256=predictor.snapshot.sha256,
            training_snapshot_version=predictor.metadata.training_snapshot.snapshot_version,
            training_git_commit=predictor.metadata.git_commit,
            mlflow_run_id=predictor.metadata.mlflow_run_id,
            as_of_utc=predictor.as_of,
        )

    @application.get("/teams")
    def teams(predictor: Predictor = Depends(get_predictor)) -> list[Team]:
        return [Team.model_validate(team) for team in predictor.teams]

    @application.post("/predict")
    def predict(
        payload: PredictionRequest, predictor: Predictor = Depends(get_predictor)
    ) -> PredictionResponse:
        try:
            probability_a, probability_b = predictor.predict(payload.team_a_id, payload.team_b_id)
        except TeamSelectionError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except Exception as exc:
            logger.exception("Prediction computation failed.")
            raise HTTPException(status_code=503, detail="Prediction computation unavailable.") from exc
        return PredictionResponse(
            team_a_id=payload.team_a_id,
            team_b_id=payload.team_b_id,
            team_a_win_probability=probability_a,
            team_b_win_probability=probability_b,
            model_version=predictor.metadata.model_version,
            data_snapshot_version=predictor.snapshot.snapshot_version,
            as_of_utc=predictor.as_of,
        )

    return application


app = create_app()
