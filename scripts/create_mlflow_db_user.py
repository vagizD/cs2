"""Create the MLflow database login from Secret Manager."""

import argparse
import json
import subprocess
from urllib.error import HTTPError
from urllib.parse import quote
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project")
    parser.add_argument("instance")
    parser.add_argument("secret")
    args = parser.parse_args()
    flags = ["--project", args.project, "--quiet"]
    password = subprocess.check_output(
        ["gcloud", "secrets", "versions", "access", "latest", "--secret", args.secret, *flags],
        text=True,
    )
    token = subprocess.check_output(["gcloud", "auth", "print-access-token", *flags], text=True).strip()
    endpoint = (
        f"https://sqladmin.googleapis.com/v1/projects/{quote(args.project, safe='')}/"
        f"instances/{quote(args.instance, safe='')}/users"
    )
    request = Request(
        endpoint,
        data=json.dumps({"name": "mlflow", "type": "BUILT_IN", "password": password}).encode(),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            operation = json.load(response)["name"]
    except HTTPError as exc:
        raise SystemExit(f"Cloud SQL user creation failed with HTTP {exc.code}.") from None
    subprocess.run(["gcloud", "sql", "operations", "wait", operation, *flags], check=True)


if __name__ == "__main__":
    main()
