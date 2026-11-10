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
ORACLE_IMAGE = "gvenzl/oracle-free:23.26.3-slim-faststart@sha256:f5ff19033860d662c821cb04eb10483fa94f14f78eae252d054291ea07028093"

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
    schema_copy=("oracle.sql", "/tmp/otel-conformance-oracle.sql"),
    initialize_command=(
        "sqlplus",
        "-L",
        "-S",
        f"{ORACLE_USER}/{ORACLE_PASSWORD}"
        f"@//127.0.0.1:{ORACLE_PORT}/{ORACLE_DATABASE}",
        "@/tmp/otel-conformance-oracle.sql",
    ),
    startup_timeout_seconds=180.0,
)


class Oracle(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            ORACLE,
            container_factory=DockerContainer,
        )
