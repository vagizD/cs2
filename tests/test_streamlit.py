import socket
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import pytest
import uvicorn
from streamlit.testing.v1 import AppTest

from api.main import create_app

APP = Path("app/streamlit_app.py")


@pytest.fixture
def streamlit_client(trained, monkeypatch):
    config, _, _, _ = trained
    api = create_app(config)
    requests = []

    @api.middleware("http")
    async def record_request(request, call_next):
        requests.append(request.url.path)
        return await call_next(request)

    server = uvicorn.Server(uvicorn.Config(api, log_level="error", ws="none"))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
        thread = Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()
        try:
            deadline = monotonic() + 10
            while thread.is_alive() and not server.started and monotonic() < deadline:
                sleep(0.05)
            assert server.started
            monkeypatch.setenv("API_BASE_URL", f"http://127.0.0.1:{port}")
            monkeypatch.syspath_prepend(str(APP.resolve().parent))
            yield AppTest.from_file(APP, default_timeout=20).run(), requests
        finally:
            server.should_exit = True
            thread.join(timeout=10)


def test_streamlit_calls_the_api_over_http(streamlit_client):
    app, requests = streamlit_client
    assert not app.exception
    app.selectbox(key="team_a").set_value(4494)
    app.selectbox(key="team_b").set_value(9565)
    app.button[0].click().run()
    assert not app.exception
    assert not app.error
    assert [metric.label for metric in app.metric] == ["MOUZ", "Vitality"]
    assert sum(float(metric.value.strip("%")) for metric in app.metric) == 100
    assert any("hltv-2026-09-08" in caption.value for caption in app.caption)

    app.selectbox(key="team_b").set_value(4494)
    app.button[0].click().run()
    assert "distinct" in app.warning[0].value
    assert requests.count("/predict") == 1


def test_tournament_renders_all_rounds_from_http_predictions(streamlit_client):
    app, requests = streamlit_client
    assert not app.exception
    assert requests.count("/predict") == 0

    predict = next(button for button in app.button if button.label == "Predict tournament")
    predict.click().run()
    assert not app.exception
    assert not app.error
    assert requests.count("/predict") == 28
    assert sum(caption.value.startswith("Advances") for caption in app.caption) == 7

    table = app.dataframe[0].value
    assert len(table) == 8
    assert table["Reach semifinals"].sum() == pytest.approx(4.0)
    assert table["Reach final"].sum() == pytest.approx(2.0)
    assert table["Win championship"].sum() == pytest.approx(1.0)
    assert app.metric[0].label == "Most likely champion"
    assert app.metric[0].value == table.iloc[0]["Team"]

    app.selectbox(key="bracket_1").set_value(app.selectbox(key="bracket_0").value)
    next(button for button in app.button if button.label == "Predict tournament").click().run()
    assert any("eight distinct" in warning.value for warning in app.warning)
    assert not app.dataframe
    assert requests.count("/predict") == 28
