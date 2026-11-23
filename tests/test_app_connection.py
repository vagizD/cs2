import runpy
from pathlib import Path
from unittest.mock import Mock

import pytest
import requests

APP = Path("app/streamlit_app.py")
BASE_URL = "http://127.0.0.1:8080"


@pytest.fixture
def app_code(monkeypatch):
    monkeypatch.syspath_prepend(str(APP.resolve().parent))
    namespace = runpy.run_path(str(APP))
    monkeypatch.setitem(namespace["request_json"].__globals__, "sleep", Mock())
    return namespace


@pytest.mark.parametrize("failure", [
    requests.ConnectionError("Starting"),
    requests.Timeout("Starting"),
    408, 429, 500, 502, 503, 504,
])
def test_team_list_retries_transient_failures(app_code, monkeypatch, failure):
    success = Mock()
    success.json.return_value = [{"team_id": 4494, "name": "MOUZ"}]
    if isinstance(failure, int):
        response = Mock(status_code=failure)
        response.raise_for_status.side_effect = requests.HTTPError(response=response)
        failure = response
    send = Mock(side_effect=[failure, success])
    monkeypatch.setattr(requests, "request", send)

    assert app_code["request_json"](BASE_URL, "GET", "/teams", retry=True) == success.json.return_value
    assert send.call_count == 2
    assert send.call_args.kwargs["timeout"] == (5, 35)


def test_validation_errors_are_not_retried(app_code, monkeypatch):
    response = Mock(status_code=422)
    response.raise_for_status.side_effect = requests.HTTPError(response=response)
    send = Mock(return_value=response)
    monkeypatch.setattr(requests, "request", send)
    with pytest.raises(requests.HTTPError):
        app_code["request_json"](BASE_URL, "POST", "/predict", retry=True)
    assert send.call_count == 1


def test_retry_is_bounded(app_code, monkeypatch):
    send = Mock(side_effect=requests.Timeout("Unavailable"))
    monkeypatch.setattr(requests, "request", send)
    with pytest.raises(requests.Timeout):
        app_code["request_json"](BASE_URL, "GET", "/teams", retry=True)
    assert send.call_count == 2


def test_invalid_json_is_not_retried(app_code, monkeypatch):
    response = Mock()
    response.json.side_effect = ValueError("Invalid JSON")
    send = Mock(return_value=response)
    monkeypatch.setattr(requests, "request", send)
    with pytest.raises(ValueError):
        app_code["request_json"](BASE_URL, "GET", "/teams", retry=True)
    assert send.call_count == 1


def test_bracket_keeps_one_retry_and_checks_pair(app_code):
    session = Mock()
    success = Mock()
    success.json.return_value = {"team_a_id": 4494, "team_b_id": 9565}
    session.request.side_effect = [requests.Timeout("Starting"), success]
    assert app_code["fetch_bracket_matchup"](BASE_URL, (4494, 9565), session) == success.json.return_value
    assert session.request.call_count == 2

    success.json.return_value = {"team_a_id": 9565, "team_b_id": 4494}
    session.request.side_effect = None
    session.request.return_value = success
    with pytest.raises(ValueError, match="different matchup"):
        app_code["fetch_bracket_matchup"](BASE_URL, (4494, 9565), session)


def test_connection_error_offers_retry_button(app_code, monkeypatch):
    namespace = app_code["main"].__globals__
    ui = Mock()
    request = Mock(side_effect=requests.Timeout("Unavailable"))
    monkeypatch.setitem(namespace, "st", ui)
    monkeypatch.setitem(namespace, "backend_url", lambda: BASE_URL)
    monkeypatch.setitem(namespace, "request_json", request)
    ui.spinner.return_value.__enter__ = Mock()
    ui.spinner.return_value.__exit__ = Mock(return_value=False)

    app_code["main"]()

    request.assert_called_once_with(BASE_URL, "GET", "/teams", retry=True)
    ui.button.assert_called_once_with("Retry connection", type="primary")
    ui.error.assert_called_once()
