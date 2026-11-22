import os
from collections import Counter
from urllib.parse import urlsplit

import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

TIMEOUT = (3.05, 10)


def backend_url() -> str:
    url = os.environ.get("API_BASE_URL")
    if not url:
        try:
            url = st.secrets.get("API_BASE_URL")
        except StreamlitSecretNotFoundError:
            url = None
    base = url.strip().rstrip("/") if isinstance(url, str) else ""
    parts = urlsplit(base)
    if parts.scheme not in {"http", "https"} or not parts.hostname or parts.query or parts.fragment:
        raise ValueError("Set API_BASE_URL to the address of the prediction service.")
    return base


def request_json(base_url, method, endpoint, **kwargs):
    response = requests.request(method, f"{base_url}{endpoint}", timeout=TIMEOUT, **kwargs)
    response.raise_for_status()
    return response.json()


def main():
    st.set_page_config(page_title="CS2 Match Predictor")
    st.title("CS2 Match Predictor")
    st.write("Choose two teams to estimate their chances of winning a Counter-Strike 2 match.")

    try:
        base_url = backend_url()
    except ValueError as exc:
        st.error(str(exc))
        return

    try:
        teams = request_json(base_url, "GET", "/teams")
    except (requests.RequestException, ValueError):
        st.error("The prediction service is unavailable. Refresh to try again.")
        return

    if len(teams) < 2:
        st.warning("The current snapshot has too few teams with recent match history.")
        return

    names = {team["team_id"]: team["name"] for team in teams}
    occurrences = Counter(names.values())

    def label(team_id):
        name = names[team_id]
        return f"{name} ({team_id})" if occurrences[name] > 1 else name

    with st.form("matchup", border=False):
        left, right = st.columns(2)
        team_a = left.selectbox("Team A", list(names), format_func=label, key="team_a")
        team_b = right.selectbox("Team B", list(names), index=1, format_func=label, key="team_b")
        submitted = st.form_submit_button("Predict match", type="primary")

    if submitted:
        if team_a == team_b:
            st.warning("Choose two distinct teams.")
        else:
            with st.spinner("Calculating probabilities…"):
                try:
                    prediction = request_json(
                        base_url, "POST", "/predict", json={"team_a_id": team_a, "team_b_id": team_b}
                    )
                except requests.Timeout:
                    st.error("The prediction took too long. Try again.")
                except (requests.RequestException, ValueError):
                    st.error("The service could not return a prediction. Refresh the team list and try again.")
                else:
                    left, right = st.columns(2)
                    for column, team_id, side in ((left, team_a, "a"), (right, team_b, "b")):
                        probability = prediction[f"team_{side}_win_probability"]
                        column.metric(label(team_id), f"{probability:.1%}")
                        column.progress(probability)
                    cutoff = prediction["as_of_utc"].replace("T", " ").removesuffix("Z")
                    st.caption(f"Data cutoff {cutoff} UTC")
                    st.caption(
                        f"Snapshot {prediction['data_snapshot_version']} · "
                        f"Model {prediction['model_version']}"
                    )

    st.caption("Estimates use historical [HLTV](https://www.hltv.org/) rankings and match results.")


if __name__ == "__main__":
    main()
