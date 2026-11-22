import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from itertools import combinations
from urllib.parse import urlsplit

import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from bracket import BRACKET_SIZE, ROUND_NAMES, BracketPrediction, bracket_predictions

TIMEOUT = (3.05, 10)
VERSION_FIELDS = ("as_of_utc", "data_snapshot_version", "model_version")


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


def matchup(base_url, team_a, team_b):
    return request_json(
        base_url, "POST", "/predict", json={"team_a_id": team_a, "team_b_id": team_b}
    )


def show_provenance(info):
    cutoff = info["as_of_utc"].replace("T", " ").removesuffix("Z")
    st.caption(f"Data cutoff {cutoff} UTC")
    st.caption(f"Snapshot {info['data_snapshot_version']} · Model {info['model_version']}")


def show_match_form(base_url, team_ids, label):
    st.write("Choose two teams to estimate their chances of winning a Counter-Strike 2 match.")
    with st.form("matchup", border=False):
        left, right = st.columns(2)
        team_a = left.selectbox("Team A", team_ids, format_func=label, key="team_a")
        team_b = right.selectbox("Team B", team_ids, index=1, format_func=label, key="team_b")
        submitted = st.form_submit_button("Predict match", type="primary")

    if not submitted:
        return
    if team_a == team_b:
        st.warning("Choose two distinct teams.")
        return
    with st.spinner("Calculating probabilities…"):
        try:
            prediction = matchup(base_url, team_a, team_b)
        except requests.Timeout:
            st.error("The prediction took too long. Try again.")
            return
        except (requests.RequestException, ValueError):
            st.error("The service could not return a prediction. Refresh the team list and try again.")
            return

    left, right = st.columns(2)
    for column, team_id, side in ((left, team_a, "a"), (right, team_b, "b")):
        probability = prediction[f"team_{side}_win_probability"]
        column.metric(label(team_id), f"{probability:.1%}")
        column.progress(probability)
    show_provenance(prediction)


def fetch_bracket(base_url, teams):
    def fetch_pair(pair):
        prediction = matchup(base_url, *pair)
        if (prediction["team_a_id"], prediction["team_b_id"]) != pair:
            raise ValueError("The API returned a different matchup.")
        return prediction

    pairs = list(combinations(sorted(teams), 2))
    with ThreadPoolExecutor(max_workers=4) as pool:
        predictions = list(pool.map(fetch_pair, pairs))

    versions = {tuple(prediction[field] for field in VERSION_FIELDS) for prediction in predictions}
    if len(versions) != 1:
        raise ValueError("The model or snapshot changed during the bracket prediction.")
    pair_probabilities = {
        pair: prediction["team_a_win_probability"]
        for pair, prediction in zip(pairs, predictions, strict=True)
    }
    return bracket_predictions(teams, pair_probabilities), dict(zip(VERSION_FIELDS, versions.pop()))


def show_bracket(result: BracketPrediction, label):
    champion = result.champion
    st.metric("Most likely champion", label(champion))
    championship_chance = result.advancement[champion][-1]
    st.progress(min(1.0, championship_chance), text=f"{championship_chance:.1%} chance to win")

    st.subheader("Projected matchups")
    st.caption("Each matchup advances its favored team. The advancement table includes all possible matchups.")
    for column, round_name, matches in zip(st.columns(3), ROUND_NAMES, result.rounds, strict=True):
        with column:
            st.markdown(f"**{round_name}**")
            for match in matches:
                with st.container(border=True):
                    st.write(f"{label(match.team_a)} · {match.probability_a:.1%}")
                    st.write(f"{label(match.team_b)} · {1.0 - match.probability_a:.1%}")
                    st.caption(f"Advances · {label(match.winner)}")

    st.subheader("Advancement probabilities")
    ordered = sorted(result.advancement, key=lambda team: result.advancement[team][-1], reverse=True)
    rows = []
    for team in ordered:
        semi, final, win = result.advancement[team]
        rows.append({
            "Team": label(team),
            "Reach semifinals": semi,
            "Reach final": final,
            "Win championship": win,
        })
    st.dataframe(
        rows, hide_index=True,
        column_config=dict.fromkeys(
            ("Reach semifinals", "Reach final", "Win championship"),
            st.column_config.NumberColumn(format="percent"),
        ),
    )


def show_tournament_form(base_url, team_ids, label):
    if len(team_ids) < BRACKET_SIZE:
        st.warning("The current snapshot needs eight eligible teams for a tournament.")
        return

    st.write(
        "Select eight distinct teams in quarterfinal order. "
        "Quarterfinals 1–2 and 3–4 lead to separate semifinals."
    )
    with st.form("tournament"):
        teams = []
        columns = st.columns(2)
        for index in range(BRACKET_SIZE // 2):
            with columns[index % len(columns)]:
                st.markdown(f"**Quarterfinal {index + 1}**")
                for offset, side in enumerate(("First team", "Second team")):
                    seed = 2 * index + offset
                    teams.append(st.selectbox(
                        side, team_ids, index=seed, format_func=label, key=f"bracket_{seed}",
                    ))
        submitted = st.form_submit_button("Predict tournament", type="primary")

    seeds = tuple(teams)
    if submitted:
        st.session_state.pop("bracket_result", None)
        if len(set(seeds)) != BRACKET_SIZE:
            st.warning("Choose eight distinct teams.")
            return
        with st.spinner("Calculating bracket probabilities…"):
            try:
                result, provenance = fetch_bracket(base_url, seeds)
            except (requests.RequestException, KeyError, TypeError, ValueError):
                st.error("The service could not complete the bracket prediction. Try again.")
                return
        st.session_state["bracket_result"] = (base_url, seeds, result, provenance)

    saved = st.session_state.get("bracket_result")
    if saved and saved[:2] == (base_url, seeds):
        show_bracket(saved[2], label)
        show_provenance(saved[3])


def main():
    st.set_page_config(page_title="CS2 Match Predictor", layout="wide")
    st.title("CS2 Match Predictor")

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

    single, tournament = st.tabs(["Single match", "Tournament bracket"])
    with single:
        show_match_form(base_url, list(names), label)
    with tournament:
        show_tournament_form(base_url, list(names), label)
    st.caption("Estimates use historical [HLTV](https://www.hltv.org/) rankings and match results.")


if __name__ == "__main__":
    main()
