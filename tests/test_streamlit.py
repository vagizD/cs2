import socket
from pathlib import Path
from threading import Thread
from time import monotonic, sleep

import uvicorn
from streamlit.testing.v1 import AppTest

from api.main import create_app

APP = Path("app/streamlit_app.py")


def test_streamlit_calls_the_api_over_http(trained, monkeypatch):
    config, _, _, _ = trained
    server = uvicorn.Server(uvicorn.Config(create_app(config), log_level="error", ws="none"))
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
            app = AppTest.from_file(APP, default_timeout=15).run()
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
        finally:
            server.should_exit = True
            thread.join(timeout=10)
