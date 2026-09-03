# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Microsoft SQL Server backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

SQL_SERVER_DATABASE = "conformance"
SQL_SERVER_USER = "sa"
SQL_SERVER_PASSWORD = "Conformance1!"
SQL_SERVER_PORT = 1433
# Microsoft moves the cumulative update through the middle of the tag, which
# `docker` versioning reads as part of an incompatible suffix rather than as a
# newer version, so this pin names the tag's parts instead.
# renovate: datasource=docker depName=mcr.microsoft.com/mssql/server versioning=regex:^(?<major>\d+)-CU(?<minor>\d+)-(?<compatibility>ubuntu-\d+\.\d+)$
SQL_SERVER_IMAGE = "mcr.microsoft.com/mssql/server:2025-CU8-ubuntu-24.04@sha256:4bab24f36c1ecd48e85f7d37df26e6bf301641d84c3fe652f9a0dcc947d512e1"
_SQLCMD = "/opt/mssql-tools18/bin/sqlcmd"

SQL_SERVER = BackendSpec(
    name="Microsoft SQL Server",
    image=SQL_SERVER_IMAGE,
    port=SQL_SERVER_PORT,
    database=SQL_SERVER_DATABASE,
    user=SQL_SERVER_USER,
    password=SQL_SERVER_PASSWORD,
    environment=(
        ("ACCEPT_EULA", "Y"),
        ("MSSQL_PID", "Developer"),
        ("MSSQL_SA_PASSWORD", SQL_SERVER_PASSWORD),
    ),
    ready_command=(
        "/bin/bash",
        "-c",
        f'SQLCMDPASSWORD="$MSSQL_SA_PASSWORD" exec {_SQLCMD} '
        '-S 127.0.0.1 -U sa -C -Q "SELECT 1"',
    ),
    schema_resource="sql_server.sql",
    schema_path="/tmp/otel-conformance-sql-server.sql",
    schema_command=(
        _SQLCMD,
        "-S",
        "127.0.0.1",
        "-U",
        SQL_SERVER_USER,
        "-C",
        "-b",
        "-i",
        "/tmp/otel-conformance-sql-server.sql",
    ),
    schema_environment=(("SQLCMDPASSWORD", SQL_SERVER_PASSWORD),),
)


class SQLServer(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            SQL_SERVER,
            container_factory=DockerContainer,
        )
