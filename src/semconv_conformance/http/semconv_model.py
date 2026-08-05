# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""HTTP semantic convention span type specs and metric types."""

from __future__ import annotations

from semconv_conformance.attribute_spec import AttributeSpec

SPAN_SPECS: dict[str, AttributeSpec] = {
    "client": AttributeSpec(
        label="HTTP Client",
        discriminator_attrs=frozenset(
            {
                "url.full",
                "http.request.resend_count",
            }
        ),
        required=(
            "http.request.method",
            "server.address",
            "server.port",
            "url.full",
        ),
        conditionally_required=(
            "error.type",
            "http.request.method_original",
            "http.response.status_code",
            "network.protocol.name",
        ),
        recommended=(
            "http.request.resend_count",
            "network.peer.address",
            "network.peer.port",
            "network.protocol.version",
        ),
        opt_in=(
            "http.request.body.size",
            "http.request.size",
            "http.response.body.size",
            "http.response.size",
            "network.transport",
            "url.scheme",
            "url.template",
            "user_agent.original",
            "user_agent.synthetic.type",
        ),
    ),
    "server": AttributeSpec(
        label="HTTP Server",
        discriminator_attrs=frozenset(
            {
                "url.path",
                "http.route",
                "client.address",
            }
        ),
        required=(
            "http.request.method",
            "url.path",
            "url.scheme",
        ),
        conditionally_required=(
            "error.type",
            "http.request.method_original",
            "http.response.status_code",
            "http.route",
            "network.protocol.name",
            "server.port",
            "url.query",
        ),
        recommended=(
            "client.address",
            "network.peer.address",
            "network.peer.port",
            "network.protocol.version",
            "server.address",
            "user_agent.original",
        ),
        opt_in=(
            "client.port",
            "http.request.body.size",
            "http.request.size",
            "http.response.body.size",
            "http.response.size",
            "network.local.address",
            "network.local.port",
            "network.transport",
            "user_agent.synthetic.type",
        ),
    ),
}

SPAN_TYPE_ORDER = [
    "client",
    "server",
]

METRIC_SPECS: dict[str, AttributeSpec] = {
    "http.client.request.duration": AttributeSpec(
        label="Client Request Duration",
        required=(
            "http.request.method",
            "server.address",
            "server.port",
        ),
        conditionally_required=(
            "error.type",
            "http.response.status_code",
            "network.protocol.name",
        ),
        recommended=("network.protocol.version",),
        opt_in=(
            "url.scheme",
            "url.template",
        ),
    ),
    "http.server.request.duration": AttributeSpec(
        label="Server Request Duration",
        required=(
            "http.request.method",
            "url.scheme",
        ),
        conditionally_required=(
            "error.type",
            "http.response.status_code",
            "http.route",
            "network.protocol.name",
        ),
        recommended=("network.protocol.version",),
        opt_in=(
            "server.address",
            "server.port",
            "user_agent.synthetic.type",
        ),
    ),
}

# No HTTP-specific event types.
EVENT_SPECS: dict[str, AttributeSpec] = {}

HTTP_METRIC_TYPES: dict[str, str] = {k: v.label for k, v in METRIC_SPECS.items()}
