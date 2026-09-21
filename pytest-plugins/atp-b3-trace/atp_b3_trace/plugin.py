"""Add B3 trace/span headers to every `requests` call a pytest test makes.

Header contract (shared with the other ATP runners):
    X-B3-TraceId: <PROJECT_ID><RUN_ID><testcase_id>   fixed for one pytest test item
    X-B3-SpanId:  16 lowercase hex characters          fresh for every HTTP call
    X-B3-Sampled: 1                                    always

PROJECT_ID and RUN_ID come from the orchestrator and are used as-is. testcase_id is derived
from pytest's own node ID, so it stays the same across reruns of one test.

This module registers itself as a pytest plugin through the "pytest11" entry point, so it
loads automatically for every test suite this runner executes; no change to the test suite's
own code is required, beyond it importing `requests` to make HTTP calls.
"""

import contextvars
import hashlib
import os
import secrets

import pytest

_current_trace_id: "contextvars.ContextVar[str | None]" = contextvars.ContextVar(
    "atp_b3_trace_id", default=None
)


def _trace_id_for(nodeid: str) -> "str | None":
    """Returns the X-B3-TraceId for a pytest node ID, or None when PROJECT_ID/RUN_ID is unset."""
    project_id = os.environ.get("PROJECT_ID")
    run_id = os.environ.get("RUN_ID")
    if not project_id or not run_id:
        return None
    testcase_id = hashlib.sha1(nodeid.encode()).hexdigest()[:5]
    return f"{project_id}{run_id}{testcase_id}"


def _b3_headers(trace_id: str) -> dict:
    """Returns a fresh set of B3 headers for one HTTP call within the given trace."""
    return {
        "X-B3-TraceId": trace_id,
        "X-B3-SpanId": secrets.token_hex(8),
        "X-B3-Sampled": "1",
    }


@pytest.hookimpl(trylast=True)
def pytest_runtest_setup(item) -> None:
    """Fixes the X-B3-TraceId for `item`'s run, shared by every request the test makes.

    Runs last among `pytest_runtest_setup` implementations, after fixture setup (pytest's own
    implementation of this hook), so a PROJECT_ID/RUN_ID a fixture sets is visible here.
    """
    _current_trace_id.set(_trace_id_for(item.nodeid))


def pytest_runtest_teardown() -> None:
    """Clears the trace ID set by `pytest_runtest_setup`, so teardown code carries none."""
    _current_trace_id.set(None)


def pytest_configure() -> None:
    """Patches `requests.Session.request` to add B3 headers, when `requests` is importable."""
    try:
        import requests  # pylint: disable=import-outside-toplevel
    except ImportError:
        return
    _patch_requests_session(requests)


_SESSION_PATCHED = False


def _patch_requests_session(requests_module) -> None:
    global _SESSION_PATCHED  # pylint: disable=global-statement
    if _SESSION_PATCHED:
        return
    original_request = requests_module.Session.request

    def patched_request(self, method, url, **kwargs):
        trace_id = _current_trace_id.get()
        if trace_id:
            headers = dict(kwargs.get("headers") or {})
            headers.update(_b3_headers(trace_id))
            kwargs["headers"] = headers
        return original_request(self, method, url, **kwargs)

    requests_module.Session.request = patched_request
    _SESSION_PATCHED = True
