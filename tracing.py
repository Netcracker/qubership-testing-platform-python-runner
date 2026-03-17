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

_TRACEPARENT: str = os.environ.get("TRACEPARENT", "")


# ---------------------------------------------------------------------------
# pytest plugin entry point
# ---------------------------------------------------------------------------

def pytest_configure(config) -> None:
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
        from opentelemetry import trace as otel_trace
        from opentelemetry.propagators.textmap import default_setter

        if setter is None:
            setter = default_setter

        span_ctx = otel_trace.get_current_span(context).get_span_context()
        if not span_ctx or not span_ctx.is_valid:
            return

        setter.set(carrier, "trace-id", format(span_ctx.trace_id, "032x"))
        setter.set(carrier, "span-id", format(span_ctx.span_id, "016x"))

    def extract(self, carrier, context=None, getter=None):
        return context

    @property
    def fields(self) -> Set[str]:
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
    from opentelemetry import trace as otel_trace, context as otel_context
    from opentelemetry.trace import NonRecordingSpan, SpanContext, TraceFlags

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


def _bootstrap_otel() -> None:
    from opentelemetry import trace as otel_trace, propagate
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME
    from opentelemetry.propagators.composite import CompositePropagator
    from opentelemetry.propagators.b3 import B3MultiFormat
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

    service_name = os.environ.get("OTEL_SERVICE_NAME", "atp3-python-runner")
    resource = Resource({SERVICE_NAME: service_name})
    provider = TracerProvider(resource=resource)

    otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if otlp_endpoint:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))

    otel_trace.set_tracer_provider(provider)

    composite = CompositePropagator([
        TraceContextTextMapPropagator(),
        B3MultiFormat(),
        _TraceIdSpanIdPropagator(),
    ])
    propagate.set_global_textmap(composite)

    _attach_root_context()

    try:
        from opentelemetry.instrumentation.requests import RequestsInstrumentation
        RequestsInstrumentation().instrument()
    except ImportError:
        pass

    try:
        from opentelemetry.instrumentation.urllib3 import URLLib3Instrumentation
        URLLib3Instrumentation().instrument()
    except ImportError:
        pass

    _patch_print()


def _patch_print() -> None:
    """
    Prefix print() output with the active OTel trace ID, matching the
    [traceId=...] prefix that logging.sh prepends to bash-level logs.
    """
    _orig = builtins.print

    def _traced(*args, **kwargs):
        from opentelemetry import trace as otel_trace
        span_ctx = otel_trace.get_current_span().get_span_context()
        if span_ctx and span_ctx.is_valid:
            _orig(f"[traceId={format(span_ctx.trace_id, '032x')}]", *args, **kwargs)
        else:
            _orig(*args, **kwargs)

    builtins.print = _traced
