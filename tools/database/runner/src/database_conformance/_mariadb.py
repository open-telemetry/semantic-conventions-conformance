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
MARIADB_IMAGE = "mariadb:11.8.9-noble@sha256:2d2f4095530294735a857cfe22bb101e19b0849b416911c796ec4aa81b164a62"

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
    schema_resource="mariadb.sql",
    schema_path="/tmp/otel-conformance-mariadb.sql",
    schema_command=(
        "sh",
        "-c",
        "exec mariadb "
        f"--user={MARIADB_USER} "
        f"--database={MARIADB_DATABASE} "
        "--binary-mode < /tmp/otel-conformance-mariadb.sql",
    ),
    schema_environment=(("MYSQL_PWD", MARIADB_PASSWORD),),
)


class MariaDB(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            MARIADB,
            container_factory=DockerContainer,
        )
