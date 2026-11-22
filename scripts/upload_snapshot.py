from ml.config import config_parser, database_path, load_config
from ml.gcs import upload_snapshot


def main() -> None:
    args = config_parser("Publish an immutable SQLite snapshot to GCS.").parse_args()
    config = load_config(args.config)
    manifest = upload_snapshot(
        database_path(config), config.data.gcs_uri, config.data.snapshot_version
    )
    print(manifest.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
