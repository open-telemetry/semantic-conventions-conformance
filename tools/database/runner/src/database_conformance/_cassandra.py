# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Apache Cassandra backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

CASSANDRA_DATABASE = "conformance"
CASSANDRA_DATACENTER = "datacenter1"
CASSANDRA_PORT = 9042
# renovate: datasource=docker depName=cassandra versioning=docker
CASSANDRA_IMAGE = "cassandra:5.0.9@sha256:d35e159439b302146f964919904f84fd3c2cebf347272b8cb8c4368c1cf200e5"

CASSANDRA = BackendSpec(
    name="Cassandra",
    image=CASSANDRA_IMAGE,
    port=CASSANDRA_PORT,
    database=CASSANDRA_DATABASE,
    user="",
    password="",
    environment=(
        ("CASSANDRA_CLUSTER_NAME", "otel-conformance"),
        ("CASSANDRA_DC", CASSANDRA_DATACENTER),
        ("CASSANDRA_NUM_TOKENS", "1"),
        ("MAX_HEAP_SIZE", "256M"),
        ("HEAP_NEWSIZE", "64M"),
    ),
    ready_command=(
        "cqlsh",
        "127.0.0.1",
        str(CASSANDRA_PORT),
        "--execute",
        "SELECT release_version FROM system.local",
    ),
    schema_resource="cassandra.cql",
    schema_path="/tmp/otel-conformance-cassandra.cql",
    schema_command=(
        "cqlsh",
        "127.0.0.1",
        str(CASSANDRA_PORT),
        "--file",
        "/tmp/otel-conformance-cassandra.cql",
    ),
    variables=(("DATABASE_LOCAL_DATACENTER", CASSANDRA_DATACENTER),),
    startup_timeout=180,
)


class Cassandra(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            CASSANDRA,
            container_factory=DockerContainer,
        )
