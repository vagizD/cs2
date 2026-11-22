from ml.config import config_parser, database_path, load_config
from ml.gcs import download_snapshot


def main() -> None:
    args = config_parser("Download and verify a versioned GCS snapshot.").parse_args()
    config = load_config(args.config)
    path = database_path(config, "gcs")
    manifest = download_snapshot(path, config.data.gcs_uri, config.data.snapshot_version)
    print(f"Verified {manifest.snapshot_version} at {path} (SHA-256 {manifest.sha256}).")


if __name__ == "__main__":
    main()
