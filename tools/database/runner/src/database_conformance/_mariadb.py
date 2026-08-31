# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""MariaDB backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

MARIADB_DATABASE = "conformance"
MARIADB_USER = "conformance"
MARIADB_PASSWORD = "conformance"
MARIADB_PORT = 3306
# renovate: datasource=docker depName=mariadb versioning=docker
MARIADB_IMAGE = "mariadb:11.8.9-noble@sha256:2439dcd7d14010ecd1ff7a4e1c5abe8e208c34fe35290744deeeaac3569043c3"

MARIADB = BackendSpec(
    name="MariaDB",
    image=MARIADB_IMAGE,
    port=MARIADB_PORT,
    database=MARIADB_DATABASE,
    user=MARIADB_USER,
    password=MARIADB_PASSWORD,
    environment=(
        ("MARIADB_DATABASE", MARIADB_DATABASE),
        ("MARIADB_USER", MARIADB_USER),
        ("MARIADB_PASSWORD", MARIADB_PASSWORD),
        ("MARIADB_RANDOM_ROOT_PASSWORD", "yes"),
    ),
    ready_command=("healthcheck.sh", "--connect", "--innodb_initialized"),
    schema_copy=("mariadb.sql", "/tmp/otel-conformance-mariadb.sql"),
    initialize_command=(
        "sh",
        "-c",
        "exec mariadb "
        f"--user={MARIADB_USER} "
        f"--database={MARIADB_DATABASE} "
        "--binary-mode < /tmp/otel-conformance-mariadb.sql",
    ),
    initialize_environment=(("MYSQL_PWD", MARIADB_PASSWORD),),
)


class MariaDB(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            MARIADB,
            container_factory=DockerContainer,
        )
