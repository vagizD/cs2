import os
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from html import escape
from itertools import combinations
from pathlib import Path
from time import sleep
from urllib.parse import urlsplit

import requests
import streamlit as st
from streamlit.errors import StreamlitSecretNotFoundError

from bracket import BRACKET_SIZE, ROUND_NAMES, BracketPrediction, bracket_predictions

TIMEOUT = (3.05, 10)
BRACKET_TIMEOUT = (5, 35)
BRACKET_WORKERS = 4
RETRYABLE_STATUS = {408, 429, 500, 502, 503, 504}
BRACKET_STYLES = Path(__file__).with_name("bracket.css")
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


def request_json(base_url, method, endpoint, *, session=None, timeout=TIMEOUT, **kwargs):
    send = session.request if session else requests.request
    response = send(method, f"{base_url}{endpoint}", timeout=timeout, **kwargs)
    response.raise_for_status()
    return response.json()


def matchup(base_url, team_a, team_b, **request_options):
    return request_json(
        base_url, "POST", "/predict",
        json={"team_a_id": team_a, "team_b_id": team_b}, **request_options,
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


def fetch_bracket_matchup(base_url, pair, session):
    # Predictions are read-only. Retry a transient failure once on the same submission.
    for attempt in range(2):
        try:
            prediction = matchup(base_url, *pair, session=session, timeout=BRACKET_TIMEOUT)
        except requests.HTTPError as exc:
            if attempt or exc.response.status_code not in RETRYABLE_STATUS:
                raise
        except (requests.ConnectionError, requests.Timeout):
            if attempt:
                raise
        else:
            if (prediction["team_a_id"], prediction["team_b_id"]) != pair:
                raise ValueError("The API returned a different matchup.")
            return prediction
        sleep(0.4)


def fetch_bracket(base_url, teams):
    def fetch_chunk(pairs):
        with requests.Session() as session:
            return {pair: fetch_bracket_matchup(base_url, pair, session) for pair in pairs}

    pairs = list(combinations(sorted(teams), 2))
    chunks = [pairs[index::BRACKET_WORKERS] for index in range(BRACKET_WORKERS)]
    predictions = {}
    with ThreadPoolExecutor(max_workers=BRACKET_WORKERS) as pool:
        for chunk in pool.map(fetch_chunk, chunks):
            predictions.update(chunk)

    versions = {tuple(prediction[field] for field in VERSION_FIELDS)
                for prediction in predictions.values()}
    if len(versions) != 1:
        raise ValueError("The model or snapshot changed during the bracket prediction.")
    probabilities = {pair: prediction["team_a_win_probability"]
                     for pair, prediction in predictions.items()}
    return bracket_predictions(teams, probabilities), dict(zip(VERSION_FIELDS, versions.pop()))


def show_bracket_outcome(result: BracketPrediction, slots, winner_slot, label):
    for round_index, (matches, round_slots) in enumerate(zip(result.rounds, slots, strict=True)):
        for match, slot in zip(matches, round_slots, strict=True):
            if round_index == 0:
                winner = escape(label(match.winner))
                slot.html(
                    f'<div class="bracket-advances"><strong>{winner} advances</strong>'
                    f'<span>{match.winner_probability:.1%}</span></div>'
                )
                continue

            rows = []
            for team, probability in ((match.team_a, match.probability_a),
                                      (match.team_b, 1.0 - match.probability_a)):
                style = "bracket-team bracket-winner" if team == match.winner else "bracket-team"
                rows.append(f'<div class="{style}"><span>{escape(label(team))}</span>'
                            f'<span>{probability:.1%}</span></div>')
            slot.html("".join(rows))

    winner_slot.html(f'<strong class="bracket-champion">{escape(label(result.winner))}</strong>')
    st.caption(f"Most probable bracket · {result.probability:.2%} chance of this exact outcome")

    st.subheader("Championship odds")
    ordered = sorted(result.championship, key=result.championship.get, reverse=True)
    st.dataframe(
        [{"Team": label(team), "Win tournament": result.championship[team]} for team in ordered],
        hide_index=True,
        column_config={"Win tournament": st.column_config.NumberColumn(format="percent")},
    )


def show_tournament_form(base_url, team_ids, label):
    if len(team_ids) < BRACKET_SIZE:
        st.warning("The current snapshot needs eight eligible teams for a tournament.")
        return

    st.html(BRACKET_STYLES)
    teams = []
    slots = []
    with st.form("tournament", border=False):
        prompt, action = st.columns([3, 1], vertical_alignment="center")
        prompt.caption("Choose eight distinct teams in the quarterfinal slots.")
        submitted = action.form_submit_button("Predict tournament", type="primary")
        feedback = prompt.empty()

        with st.container(key="bracket-board"):
            columns = st.columns([1.25, 1, 1, 0.75], gap="large")
            for round_index, (column, name, track) in enumerate(
                zip(columns[:3], ROUND_NAMES, ("quarter", "semi", "final"), strict=True)
            ):
                with column:
                    st.markdown(f"**{name}**")
                    round_slots = []
                    with st.container(key=f"bracket-track-{track}"):
                        for index in range(BRACKET_SIZE // (2 ** (round_index + 1))):
                            with st.container(key=f"bracket-card-{track}-{index}", gap=None):
                                if round_index == 0:
                                    for offset in range(2):
                                        seed = 2 * index + offset
                                        teams.append(st.selectbox(
                                            f"Quarterfinal {index + 1}, team {offset + 1}",
                                            team_ids, index=seed, format_func=label,
                                            key=f"bracket_{seed}", label_visibility="collapsed",
                                        ))
                                slot = st.empty()
                                round_slots.append(slot)
                                if round_index > 0:
                                    slot.html('<p class="bracket-placeholder">Awaiting winners</p>')
                    slots.append(round_slots)

            with columns[-1]:
                st.markdown("**Champion**")
                with st.container(key="bracket-track-winner"):
                    with st.container(key="bracket-card-winner"):
                        winner_slot = st.empty()
                        winner_slot.html('<p class="bracket-placeholder">To be decided</p>')

    seeds = tuple(teams)
    if submitted:
        st.session_state.pop("tournament_outcome", None)
        if len(set(seeds)) != BRACKET_SIZE:
            feedback.warning("Choose eight distinct teams.")
            return
        with feedback.container(), st.spinner("Calculating bracket probabilities…"):
            try:
                result, provenance = fetch_bracket(base_url, seeds)
            except requests.Timeout:
                feedback.error("The prediction service timed out after retrying. Try again in a moment.")
                return
            except (requests.RequestException, KeyError, TypeError, ValueError):
                feedback.error("The service could not complete the bracket prediction. Try again.")
                return
        feedback.empty()
        st.session_state["tournament_outcome"] = (base_url, seeds, result, provenance)

    saved = st.session_state.get("tournament_outcome")
    if saved and saved[:2] == (base_url, seeds):
        show_bracket_outcome(saved[2], slots, winner_slot, label)
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
