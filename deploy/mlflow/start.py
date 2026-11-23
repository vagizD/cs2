"""Start MLflow with the Cloud Run service identity and Cloud SQL socket."""

import os

from sqlalchemy.engine import URL


def main() -> None:
    database = URL.create(
        "postgresql+psycopg2",
        username=os.environ["DB_USER"],
        password=os.environ.pop("DB_PASSWORD"),
        database=os.environ["DB_NAME"],
        query={"host": f"/cloudsql/{os.environ['CLOUD_SQL_CONNECTION']}"},
    )
    os.environ["MLFLOW_BACKEND_STORE_URI"] = database.render_as_string(hide_password=False)
    os.execvp("mlflow", [
        "mlflow", "server", "--host", "0.0.0.0", "--port", os.environ.get("PORT", "8080"),
        "--workers", "1", "--serve-artifacts",
        "--artifacts-destination", os.environ["MLFLOW_ARTIFACT_DESTINATION"],
        "--allowed-hosts", "localhost,127.0.0.1,*.run.app",
    ])


if __name__ == "__main__":
    main()
