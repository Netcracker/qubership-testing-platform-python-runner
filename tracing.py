# Copyright 2024-2025 NetCracker Technology Corporation
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
OpenTelemetry tracing bootstrap for atp3-python-runner.

Loaded as a pytest plugin via PYTEST_ADDOPTS="-p tracing".

Reads the trace context produced by trace-init.sh from environment variables
and auto-instruments outgoing HTTP requests (requests, urllib3) so that
B3, W3C traceparent, and NC custom trace-id/span-id headers are injected
on every HTTP call — mirroring what tracing.js does for Node.js runners.

Headers injected on every outgoing HTTP request:
  traceparent          — W3C Trace Context
  x-b3-traceid        ┐
  x-b3-spanid         ├─ Zipkin/B3 multi-header
  x-b3-sampled        ┘
  trace-id            ┐
  span-id             ┘─ Custom headers

If TRACEPARENT is absent (e.g. local dev run), setup is skipped entirely.
"""
from __future__ import annotations

import builtins
import os
from typing import Optional, Set

from opentelemetry.sdk.trace import TracerProvider

# opentelemetry packages are available at runtime but not in the linter env
# pylint: disable=import-error


_TRACEPARENT: str = os.environ.get("TRACEPARENT", "")
_provider: Optional["TracerProvider"] = None


# ---------------------------------------------------------------------------
# Public API for tests (span flush before exit)
# ---------------------------------------------------------------------------


def force_flush(timeout_millis: int = 5000) -> bool:
    """
    Flush pending spans to the OTLP exporter.
    Call before process exit so spans reach Jaeger in CI/Docker runs.
    Returns True if no provider or flush succeeded.
    """
    if _provider is None:
        return True
    return _provider.force_flush(timeout_millis)


# ---------------------------------------------------------------------------
# pytest plugin entry point
# ---------------------------------------------------------------------------


def pytest_configure(config) -> None:  # pylint: disable=unused-argument
    """Called once per worker process before test collection starts."""
    if not _TRACEPARENT:
        return
    _bootstrap_otel()


# ---------------------------------------------------------------------------
# Custom headers propagator
# ---------------------------------------------------------------------------


class _TraceIdSpanIdPropagator:
    """
    Minimal propagator that injects 'trace-id' and 'span-id' headers
    (lowercase, hyphenated) expected by custom services.

    extract() is intentionally a no-op — we only inject.
    """

    _FIELDS: Set[str] = {"trace-id", "span-id"}

    def inject(self, carrier, context: Optional[object] = None, setter=None) -> None:
        """
        Minimal propagator for injecting custom 'trace-id' and 'span-id' headers.

        This class implements a propagator conforming to the OpenTelemetry propagators API,
        but tailored for systems that expect lowercase, hyphenated 'trace-id' and 'span-id'
        headers instead of standard OTel formats.

        The propagator only performs injection (outbound context propagation) and does not
        extract or parse incoming headers (extract() is a no-op). This is useful for test
        environments or systems with custom trace context expectations.

        Attributes:
            _FIELDS (Set[str]): The set of field names injected by this propagator.

        Methods:
            inject(carrier, context=None, setter=None):
                Injects 'trace-id' and 'span-id' headers into the provided carrier
                using the current span context.

            extract(carrier, context=None, getter=None):
                No-op. Returns the context unmodified.

            fields:
                Returns the set of header names injected by this propagator.
        """
        # pylint: disable=import-outside-toplevel
        from opentelemetry import trace as otel_trace
        from opentelemetry.propagators.textmap import default_setter

        # pylint: enable=import-outside-toplevel

        if setter is None:
            setter = default_setter

        span_ctx = otel_trace.get_current_span(context).get_span_context()
        if not span_ctx or not span_ctx.is_valid:
            return

        setter.set(carrier, "trace-id", format(span_ctx.trace_id, "032x"))
        setter.set(carrier, "span-id", format(span_ctx.span_id, "016x"))

    def extract(self, _carrier, context=None, _getter=None):
        """
        Returns the docstring for the _TraceIdSpanIdPropagator class.

        :return: The class docstring.
        :rtype: str
        """
        return context

    @property
    def fields(self) -> Set[str]:
        """
        Returns the docstring for the _TraceIdSpanIdPropagator class.

        :return: The class docstring as a string.
        :rtype: str
        """
        return self._FIELDS


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _attach_root_context() -> None:
    """
    Reconstruct the root SpanContext from the bash-generated TRACEPARENT env
    var and attach it to the running context so every span created during the
    test session inherits the same trace ID.
    """
    # pylint: disable=import-outside-toplevel
    from opentelemetry import context as otel_context
    from opentelemetry import trace as otel_trace
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

    # pylint: enable=import-outside-toplevel

    parts = _TRACEPARENT.split("-")
    if len(parts) != 4:
        return
    try:
        span_ctx = SpanContext(
            trace_id=int(parts[1], 16),
            span_id=int(parts[2], 16),
            is_remote=True,
            trace_flags=TraceFlags(int(parts[3], 16)),
        )
        root_ctx = otel_trace.set_span_in_context(NonRecordingSpan(span_ctx))
        otel_context.attach(root_ctx)
    except (ValueError, IndexError):
        pass


def _create_provider():
    """Build a TracerProvider with a service-name resource and return it."""
    # pylint: disable=import-outside-toplevel
    from opentelemetry.sdk.resources import SERVICE_NAME, Resource

    # pylint: enable=import-outside-toplevel

    service_name = os.environ.get("OTEL_SERVICE_NAME", "atp3-python-runner")
    resource = Resource({SERVICE_NAME: service_name})
    return TracerProvider(resource=resource)


def _add_otlp_exporter(provider) -> None:
    """Attach a BatchSpanProcessor with OTLPSpanExporter if an endpoint is configured."""
    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not otlp_endpoint:
        return
    # pylint: disable=import-outside-toplevel
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    # pylint: enable=import-outside-toplevel

    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))


def _setup_propagators(provider) -> None:
    """Register the tracer provider and composite propagator globally."""
    # pylint: disable=import-outside-toplevel
    from opentelemetry import propagate
    from opentelemetry import trace as otel_trace
    from opentelemetry.propagators.b3 import B3MultiFormat
    from opentelemetry.propagators.composite import CompositePropagator
    from opentelemetry.trace.propagation.tracecontext import (
        TraceContextTextMapPropagator,
    )

    # pylint: enable=import-outside-toplevel

    otel_trace.set_tracer_provider(provider)
    composite = CompositePropagator(
        [
            TraceContextTextMapPropagator(),
            B3MultiFormat(),
            _TraceIdSpanIdPropagator(),
        ]
    )
    propagate.set_global_textmap(composite)


def _instrument_http() -> None:
    """Auto-instrument outgoing HTTP calls via requests and urllib3 if available."""
    try:
        # pylint: disable=import-outside-toplevel
        from opentelemetry.instrumentation.requests import RequestsInstrumentor

        # pylint: enable=import-outside-toplevel
        RequestsInstrumentor().instrument()
    except ImportError as e:
        print("RequestsInstrumentation import error, skipping tracing.", e.name, e.path)

    try:
        # pylint: disable=import-outside-toplevel
        from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentor

        # pylint: enable=import-outside-toplevel
        URLLib3Instrumentor().instrument()
    except ImportError as e:
        print("URLLib3Instrumentation import error, skipping tracing.", e.name, e.path)


def _bootstrap_otel() -> None:
    """Orchestrate OTel initialisation: provider, exporter, propagators, instrumentation."""
    global _provider  # pylint: disable=global-statement
    _provider = _create_provider()
    _add_otlp_exporter(_provider)
    _setup_propagators(_provider)
    _attach_root_context()
    _instrument_http()
    _patch_print()


def _patch_print() -> None:
    """
    Prefix print() output with the active OTel trace ID, matching the
    [traceId=...] prefix that logging.sh prepends to bash-level logs.
    """
    _orig = builtins.print

    def _traced(*args, **kwargs):
        # pylint: disable=import-outside-toplevel
        from opentelemetry import trace as otel_trace

        # pylint: enable=import-outside-toplevel

        span_ctx = otel_trace.get_current_span().get_span_context()
        if span_ctx and span_ctx.is_valid:
            _orig(f"[traceId={format(span_ctx.trace_id, '032x')}]", *args, **kwargs)
        else:
            _orig(*args, **kwargs)

    builtins.print = _traced
