# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Oracle Database backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

ORACLE_DATABASE = "FREEPDB1"
ORACLE_USER = "conformance"
ORACLE_PASSWORD = "conformance"
ORACLE_PORT = 1521
# renovate: datasource=docker depName=gvenzl/oracle-free versioning=docker
ORACLE_IMAGE = "gvenzl/oracle-free:23.26.2-slim-faststart@sha256:d8913e4e4769b6e60197949bef30a4391713afe662b4b4e71a2665c881bdac8b"

ORACLE = BackendSpec(
    name="Oracle Database",
    image=ORACLE_IMAGE,
    port=ORACLE_PORT,
    database=ORACLE_DATABASE,
    user=ORACLE_USER,
    password=ORACLE_PASSWORD,
    environment=(
        ("ORACLE_PASSWORD", ORACLE_PASSWORD),
        ("APP_USER", ORACLE_USER),
        ("APP_USER_PASSWORD", ORACLE_PASSWORD),
    ),
    ready_command=("healthcheck.sh",),
    schema_resource="oracle.sql",
    schema_path="/tmp/otel-conformance-oracle.sql",
    schema_command=(
        "sqlplus",
        "-L",
        "-S",
        f"{ORACLE_USER}/{ORACLE_PASSWORD}"
        f"@//127.0.0.1:{ORACLE_PORT}/{ORACLE_DATABASE}",
        "@/tmp/otel-conformance-oracle.sql",
    ),
    startup_timeout=("OTEL_CONFORMANCE_ORACLE_STARTUP_TIMEOUT", 180.0),
)


class Oracle(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            ORACLE,
            container_factory=DockerContainer,
        )
