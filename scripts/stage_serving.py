"""Stage the serving build context with a validated snapshot and model."""

import shutil
import tempfile
from pathlib import Path

import yaml

from ml.config import config_parser, load_config
from ml.model_artifact import METADATA_FILE, PIPELINE_FILE, load_model
from ml.predict import Predictor
from ml.snapshot import manifest_path, sha256_file

BUILD_CONTEXT = Path("artifacts/deploy")
IMAGE_DATA_DIR = "/app/serving-data"


def main() -> None:
    parser = config_parser("Stage the model and database for Docker's serving target.")
    parser.add_argument("--require-gcs", action="store_true", help="Require a verified GCS manifest.")
    args = parser.parse_args()
    config = load_config(args.config)
    predictor = Predictor(config)
    snapshot = predictor.snapshot
    if args.require_gcs and not (snapshot.gcs_uri and snapshot.gcs_generation):
        raise ValueError("Stage the SQLite snapshot downloaded from GCS for cloud deployment.")

    BUILD_CONTEXT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=BUILD_CONTEXT) as workspace:
        stage = Path(workspace)
        database = stage / "hltv_database.db"
        shutil.copyfile(predictor.path, database)
        if sha256_file(database) != snapshot.sha256:
            raise ValueError("The serving snapshot changed while staging.")
        manifest_path(database).write_text(snapshot.model_dump_json(indent=2) + "\n", encoding="utf-8")

        model_dir = stage / "model"
        model_dir.mkdir()
        for name in (PIPELINE_FILE, METADATA_FILE):
            shutil.copyfile(config.model_path / name, model_dir / name)
        _, staged_model = load_model(model_dir)
        if staged_model != predictor.metadata:
            raise ValueError("The model changed while staging.")

        staged_config = config.model_dump(mode="json")
        staged_config["artifacts_dir"] = IMAGE_DATA_DIR
        staged_config["data"]["local_db_path"] = f"{IMAGE_DATA_DIR}/hltv_database.db"
        (stage / "config.yaml").write_text(yaml.safe_dump(staged_config), encoding="utf-8")
        files = [database, manifest_path(database), stage / "config.yaml",
                 model_dir / PIPELINE_FILE, model_dir / METADATA_FILE]
        for file in files:
            target = BUILD_CONTEXT / file.relative_to(stage)
            target.parent.mkdir(parents=True, exist_ok=True)
            file.replace(target)
    print(f"Staged {staged_model.model_version} and {snapshot.snapshot_version} in {BUILD_CONTEXT}.")


if __name__ == "__main__":
    main()
