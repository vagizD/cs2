"""Verify a running predictor over HTTP or HTTPS."""

import argparse
import json
import math
from time import monotonic, sleep
from urllib.request import Request, urlopen


def read_json(url, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(url, data=body, headers={"Content-Type": "application/json"} if body else {})
    with urlopen(request, timeout=5) as response:
        return json.load(response)


def smoke(
    base_url, wait_seconds=0, team_ids=None, snapshot_version=None, git_commit=None, mlflow_run_id=None
):
    base_url = base_url.rstrip("/")
    deadline = monotonic() + wait_seconds
    expected = {
        "data_snapshot_version": snapshot_version,
        "training_git_commit": git_commit,
        "mlflow_run_id": mlflow_run_id,
    }
    while True:
        try:
            health = read_json(f"{base_url}/health")
            if health["ready"] is not True:
                raise RuntimeError("API reported that it is not ready.")
            for field, value in expected.items():
                if value is not None and health.get(field) != value:
                    raise RuntimeError(f"API returned a different {field} than expected.")
            break
        except (OSError, RuntimeError):
            if monotonic() >= deadline:
                raise
            sleep(min(1, max(0, deadline - monotonic())))

    teams = {team["team_id"]: team["name"] for team in read_json(f"{base_url}/teams")}
    team_a, team_b = team_ids or tuple(teams)[:2]
    assert team_a != team_b and {team_a, team_b} <= teams.keys()
    payload = {"team_a_id": team_a, "team_b_id": team_b}
    result = read_json(f"{base_url}/predict", payload)
    reverse = read_json(f"{base_url}/predict", {"team_a_id": team_b, "team_b_id": team_a})
    assert result["team_a_id"] == team_a and result["team_b_id"] == team_b
    p_a, p_b = result["team_a_win_probability"], result["team_b_win_probability"]
    assert 0 <= p_a <= 1 and 0 <= p_b <= 1
    assert math.isclose(p_a + p_b, 1, abs_tol=1e-12)
    assert math.isclose(p_a, reverse["team_b_win_probability"], abs_tol=1e-12)
    assert math.isclose(p_b, reverse["team_a_win_probability"], abs_tol=1e-12)
    for field in ("as_of_utc", "model_version", "data_snapshot_version"):
        assert result[field] == reverse[field] == health[field]
    print(json.dumps({"health": health, "teams": len(teams),
                      "matchup": [teams[team_a], teams[team_b]], "prediction": result}, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("base_url")
    parser.add_argument("--wait-seconds", type=float, default=0)
    parser.add_argument("--team-ids", nargs=2, type=int)
    parser.add_argument("--snapshot-version")
    parser.add_argument("--git-commit")
    parser.add_argument("--mlflow-run-id")
    args = parser.parse_args()
    smoke(
        args.base_url, args.wait_seconds, args.team_ids, args.snapshot_version,
        args.git_commit, args.mlflow_run_id,
    )


if __name__ == "__main__":
    main()
