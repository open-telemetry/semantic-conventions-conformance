# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""MySQL backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

MYSQL_DATABASE = "conformance"
MYSQL_USER = "conformance"
MYSQL_PASSWORD = "conformance"
MYSQL_PORT = 3306
# renovate: datasource=docker depName=mysql versioning=docker
MYSQL_IMAGE = "mysql:9.7.2-oraclelinux9@sha256:257388edf9c84dbc04c763625446d5f3fa6ed60d1b0873bc552c614ba0a7ab4e"

MYSQL = BackendSpec(
    name="MySQL",
    image=MYSQL_IMAGE,
    port=MYSQL_PORT,
    database=MYSQL_DATABASE,
    user=MYSQL_USER,
    password=MYSQL_PASSWORD,
    environment=(
        ("MYSQL_DATABASE", MYSQL_DATABASE),
        ("MYSQL_USER", MYSQL_USER),
        ("MYSQL_PASSWORD", MYSQL_PASSWORD),
        ("MYSQL_RANDOM_ROOT_PASSWORD", "yes"),
    ),
    ready_command=(
        "mysqladmin",
        "ping",
        "--host=127.0.0.1",
        f"--user={MYSQL_USER}",
        f"--password={MYSQL_PASSWORD}",
        "--silent",
    ),
    schema_resource="mysql.sql",
    schema_path="/tmp/otel-conformance-mysql.sql",
    schema_command=(
        "sh",
        "-c",
        "exec mysql "
        f"--user={MYSQL_USER} "
        f"--database={MYSQL_DATABASE} "
        "--binary-mode < /tmp/otel-conformance-mysql.sql",
    ),
    schema_environment=(("MYSQL_PWD", MYSQL_PASSWORD),),
    startup_timeout_seconds=120.0,
)


class MySQL(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            MYSQL,
            container_factory=DockerContainer,
        )
