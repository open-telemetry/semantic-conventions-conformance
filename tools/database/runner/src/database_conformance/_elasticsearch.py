# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Elasticsearch backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

ELASTICSEARCH_INDEX = "conformance"
ELASTICSEARCH_PORT = 9200
ELASTICSEARCH_TRANSPORT_PORT = 9300
# renovate: datasource=docker depName=docker.elastic.co/elasticsearch/elasticsearch versioning=docker
ELASTICSEARCH_IMAGE = "docker.elastic.co/elasticsearch/elasticsearch:7.17.29@sha256:3f55a7f6f29b95345dc33808d6e914f81d125d4ca90a414e26c81a3521400980"

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
    schema_resource="elasticsearch.json",
    schema_path="/tmp/otel-conformance-elasticsearch.json",
    schema_command=(
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
    additional_ports=(
        ("DATABASE_TRANSPORT_PORT", ELASTICSEARCH_TRANSPORT_PORT),
    ),
)


class Elasticsearch(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            ELASTICSEARCH,
            container_factory=DockerContainer,
        )
