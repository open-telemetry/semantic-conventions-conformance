# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Elasticsearch backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

ELASTICSEARCH_INDEX = "conformance"
ELASTICSEARCH_PORT = 9200
# renovate: datasource=docker depName=docker.elastic.co/elasticsearch/elasticsearch versioning=docker
ELASTICSEARCH_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:9.5.7@sha256:8aa3b18f6a26880f4c2fa1ffb37a48213e201b0b6a1a47412c66b1f5d533de91"

ELASTICSEARCH = BackendSpec(
    name="Elasticsearch",
    image=ELASTICSEARCH_IMAGE,
    port=ELASTICSEARCH_PORT,
    database=ELASTICSEARCH_INDEX,
    user="",
    password="",
    environment=(
        ("discovery.type", "single-node"),
        ("xpack.security.enabled", "false"),
        ("ES_JAVA_OPTS", "-Xms256m -Xmx256m"),
    ),
    ready_command=(
        "sh",
        "-c",
        "curl --fail --silent "
        f"'http://127.0.0.1:{ELASTICSEARCH_PORT}/_cluster/health"
        "?wait_for_status=yellow&timeout=1s' "
        "| grep --quiet '\"timed_out\":false'",
    ),
    schema_copy=(
        "elasticsearch.json",
        "/tmp/otel-conformance-elasticsearch.json",
    ),
    initialize_command=(
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "--header",
        "Content-Type: application/json",
        "--request",
        "PUT",
        f"http://127.0.0.1:{ELASTICSEARCH_PORT}/{ELASTICSEARCH_INDEX}",
        "--data-binary",
        "@/tmp/otel-conformance-elasticsearch.json",
    ),
)


class Elasticsearch(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            ELASTICSEARCH,
            container_factory=DockerContainer,
        )
