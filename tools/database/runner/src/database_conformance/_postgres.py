# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""PostgreSQL backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

POSTGRES_DATABASE = "conformance"
POSTGRES_USER = "conformance"
POSTGRES_PASSWORD = "conformance"
POSTGRES_PORT = 5432
# renovate: datasource=docker depName=postgres versioning=docker
POSTGRES_IMAGE = "postgres:18.6-bookworm@sha256:1c59e2c3c818eaa0f0628f695b36e7c9e362d6b219b36a54a32df645cbd7e1af"

POSTGRES = BackendSpec(
    name="PostgreSQL",
    image=POSTGRES_IMAGE,
    port=POSTGRES_PORT,
    database=POSTGRES_DATABASE,
    user=POSTGRES_USER,
    password=POSTGRES_PASSWORD,
    environment=(
        ("POSTGRES_DB", POSTGRES_DATABASE),
        ("POSTGRES_USER", POSTGRES_USER),
        ("POSTGRES_PASSWORD", POSTGRES_PASSWORD),
    ),
    ready_command=(
        "pg_isready",
        "--host",
        "127.0.0.1",
        "--port",
        str(POSTGRES_PORT),
        "--username",
        POSTGRES_USER,
        "--dbname",
        POSTGRES_DATABASE,
    ),
    schema_resource="postgres.sql",
    schema_path="/tmp/otel-conformance-postgres.sql",
    schema_command=(
        "psql",
        "--no-psqlrc",
        "--set",
        "ON_ERROR_STOP=1",
        "--host",
        "127.0.0.1",
        "--port",
        str(POSTGRES_PORT),
        "--username",
        POSTGRES_USER,
        "--dbname",
        POSTGRES_DATABASE,
        "--file",
        "/tmp/otel-conformance-postgres.sql",
    ),
    schema_environment=(("PGPASSWORD", POSTGRES_PASSWORD),),
)


class Postgres(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            POSTGRES,
            container_factory=DockerContainer,
        )
