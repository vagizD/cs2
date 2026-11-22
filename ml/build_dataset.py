"""Build a checked dataset from the frozen SQLite snapshot."""

import json
import tempfile
from pathlib import Path

from ml.config import Config, config_parser, database_path, load_config
from ml.features import feature_schema, training_examples
from ml.snapshot import Snapshot, open_snapshot, sha256_file


def build_dataset(config: Config, path: Path, snapshot: Snapshot) -> dict:
    examples = training_examples(path, config.data.lookback_days)
    if examples.empty:
        raise ValueError("No finalized historical matches found.")
    if sha256_file(path) != snapshot.sha256:
        raise ValueError("Snapshot changed before or during feature extraction.")

    output = config.artifacts_dir / "dataset"
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output) as workspace:
        staged = Path(workspace)
        csv = staged / "features.csv"
        examples.to_csv(csv, index=False, float_format="%.17g", lineterminator="\n")
        metadata = {
            "snapshot": snapshot.model_dump(mode="json"),
            "rows": len(examples),
            "features_sha256": sha256_file(csv),
            "feature_schema": feature_schema(),
            "lookback_days": list(config.data.lookback_days),
        }
        report = staged / "dataset.json"
        report.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
        csv.replace(output / csv.name)
        report.replace(output / report.name)
    return metadata


def main() -> None:
    parser = config_parser("Build point-in-time CS2 training features.")
    parser.add_argument("--source", choices=("local", "gcs"), default="local")
    args = parser.parse_args()
    config = load_config(args.config)
    path = database_path(config, args.source)
    if args.source == "gcs":
        from ml.gcs import download_snapshot

        snapshot = download_snapshot(path, config.data.gcs_uri, config.data.snapshot_version)
    else:
        snapshot = open_snapshot(path, config.data.snapshot_version)
    result = build_dataset(config, path, snapshot)
    print(f"Built {result['rows']} examples (SHA-256 {result['features_sha256']}).")


if __name__ == "__main__":
    main()
