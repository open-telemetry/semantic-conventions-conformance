# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Backend selectors and their construction and semantic-convention metadata."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from ._container import DatabaseContainer
from ._hbase import HBase
from ._mariadb import MariaDB
from ._postgres import Postgres
from ._redis import Redis
from ._sql_server import SQLServer


@dataclass(frozen=True)
class BackendRegistration:
    factory: Callable[[], DatabaseContainer]
    system: str
    client_span_type: str


BACKENDS = {
    "hbase": BackendRegistration(HBase, "hbase", "db.hbase.client"),
    "mariadb": BackendRegistration(MariaDB, "mariadb", "db.mariadb.client"),
    "postgresql": BackendRegistration(
        Postgres, "postgresql", "db.postgresql.client"
    ),
    "redis": BackendRegistration(Redis, "redis", "db.redis.client"),
    "sql_server": BackendRegistration(
        SQLServer, "microsoft.sql_server", "db.sql_server.client"
    ),
}
