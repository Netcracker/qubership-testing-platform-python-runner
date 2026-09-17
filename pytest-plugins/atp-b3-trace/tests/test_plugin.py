import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest
import requests

from atp_b3_trace.plugin import _trace_id_for


class _RecordingHandler(BaseHTTPRequestHandler):
    received_headers = []

    def do_GET(self):
        self.received_headers.append(dict(self.headers))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format, *args):
        pass


@pytest.fixture
def b3_env(monkeypatch):
    # Setting env vars here, rather than in a test body, matters: pytest_runtest_setup (which
    # fixes the trace ID for the test) runs during the setup phase, before the test body.
    monkeypatch.setenv("PROJECT_ID", "proj")
    monkeypatch.setenv("RUN_ID", "run1")


@pytest.fixture
def echo_server():
    _RecordingHandler.received_headers = []
    server = HTTPServer(("127.0.0.1", 0), _RecordingHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/", _RecordingHandler.received_headers
    finally:
        server.shutdown()
        thread.join()


def test_trace_id_is_stable_for_the_same_nodeid(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "proj")
    monkeypatch.setenv("RUN_ID", "run1")
    assert _trace_id_for("test_mod.py::test_a") == _trace_id_for("test_mod.py::test_a")


def test_trace_id_differs_across_nodeids(monkeypatch):
    monkeypatch.setenv("PROJECT_ID", "proj")
    monkeypatch.setenv("RUN_ID", "run1")
    assert _trace_id_for("test_mod.py::test_a") != _trace_id_for("test_mod.py::test_b")


def test_trace_id_is_none_without_project_id_and_run_id(monkeypatch):
    monkeypatch.delenv("PROJECT_ID", raising=False)
    monkeypatch.delenv("RUN_ID", raising=False)
    assert _trace_id_for("test_mod.py::test_a") is None


def test_requests_get_carries_b3_headers(b3_env, echo_server):
    url, received = echo_server

    requests.get(url)
    requests.get(url)

    assert len(received) == 2
    assert received[0]["X-B3-TraceId"] == received[1]["X-B3-TraceId"]
    assert received[0]["X-B3-Sampled"] == "1"
    assert received[1]["X-B3-Sampled"] == "1"
    assert received[0]["X-B3-SpanId"] != received[1]["X-B3-SpanId"]
    assert len(received[0]["X-B3-SpanId"]) == 16


def test_requests_get_carries_no_b3_headers_without_project_id(echo_server, monkeypatch):
    monkeypatch.delenv("PROJECT_ID", raising=False)
    monkeypatch.delenv("RUN_ID", raising=False)
    url, received = echo_server

    requests.get(url)

    assert "X-B3-TraceId" not in received[0]
