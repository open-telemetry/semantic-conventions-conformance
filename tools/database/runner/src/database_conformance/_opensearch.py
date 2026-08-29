# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""OpenSearch backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

OPENSEARCH_INDEX = "conformance"
OPENSEARCH_PORT = 9200
# renovate: datasource=docker depName=opensearchproject/opensearch versioning=docker
OPENSEARCH_IMAGE = "opensearchproject/opensearch:3.8.0@sha256:bcc1797519726ceb6d651d4a3e60b7c30da91793914a8dfe75fd441d4f641509"

OPENSEARCH = BackendSpec(
    name="OpenSearch",
    image=OPENSEARCH_IMAGE,
    port=OPENSEARCH_PORT,
    database=OPENSEARCH_INDEX,
    user="",
    password="",
    environment=(
        ("discovery.type", "single-node"),
        ("DISABLE_INSTALL_DEMO_CONFIG", "true"),
        ("DISABLE_SECURITY_PLUGIN", "true"),
        (
            "OPENSEARCH_JAVA_OPTS",
            "-Xms512m -Xmx512m -Dlog4j2.disable.jmx=true",
        ),
    ),
    ready_command=(
        "curl",
        "--fail",
        "--silent",
        "--show-error",
        "http://127.0.0.1:9200/_cluster/health"
        "?wait_for_status=yellow&timeout=1s",
    ),
    bootstrap_resource="opensearch-bootstrap.sh",
    bootstrap_path="/tmp/otel-conformance-opensearch.sh",
    bootstrap_command=(
        "sh",
        "/tmp/otel-conformance-opensearch.sh",
    ),
    startup_timeout_seconds=180.0,
)


class OpenSearch(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            OPENSEARCH,
            container_factory=DockerContainer,
        )
