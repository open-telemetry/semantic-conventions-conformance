# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""MongoDB backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

MONGODB_DATABASE = "conformance"
MONGODB_USER = "conformance"
MONGODB_PASSWORD = "conformance"
MONGODB_ROOT_USER = "root"
MONGODB_ROOT_PASSWORD = "conformance-root"
MONGODB_PORT = 27017
# renovate: datasource=docker depName=mongo versioning=docker
MONGODB_IMAGE = "mongo:8.0.29-noble@sha256:021b2d5ae9d253f2cca17491cc8d03aed8df3c840f3252066aa62d3277fc406e"

MONGODB = BackendSpec(
    name="MongoDB",
    image=MONGODB_IMAGE,
    port=MONGODB_PORT,
    database=MONGODB_DATABASE,
    user=MONGODB_USER,
    password=MONGODB_PASSWORD,
    environment=(
        ("MONGO_INITDB_ROOT_USERNAME", MONGODB_ROOT_USER),
        ("MONGO_INITDB_ROOT_PASSWORD", MONGODB_ROOT_PASSWORD),
    ),
    ready_command=(
        "mongosh",
        "--quiet",
        "--host",
        "127.0.0.1",
        "--port",
        str(MONGODB_PORT),
        "--username",
        MONGODB_ROOT_USER,
        "--password",
        MONGODB_ROOT_PASSWORD,
        "--authenticationDatabase",
        "admin",
        "--eval",
        "quit(db.adminCommand('ping').ok ? 0 : 1)",
    ),
    schema_resource="mongodb.js",
    schema_path="/tmp/otel-conformance-mongodb.js",
    schema_command=(
        "mongosh",
        "--quiet",
        "--host",
        "127.0.0.1",
        "--port",
        str(MONGODB_PORT),
        "--username",
        MONGODB_ROOT_USER,
        "--password",
        MONGODB_ROOT_PASSWORD,
        "--authenticationDatabase",
        "admin",
        "--file",
        "/tmp/otel-conformance-mongodb.js",
    ),
)


class MongoDB(DatabaseContainer):
    def __init__(self) -> None:
        super().__init__(
            MONGODB,
            container_factory=DockerContainer,
        )
