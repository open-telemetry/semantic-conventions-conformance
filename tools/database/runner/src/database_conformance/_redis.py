# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Redis backend definition."""

from __future__ import annotations

from testcontainers.core.container import DockerContainer

from ._container import BackendSpec, DatabaseContainer

REDIS_DATABASE = "0"
REDIS_USER = "default"
REDIS_PASSWORD = ""
REDIS_PORT = 6379
# renovate: datasource=docker depName=redis versioning=docker
REDIS_IMAGE = "redis:8.2.1-bookworm@sha256:5fa2edb1e408fa8235e6db8fab01d1afaaae96c9403ba67b70feceb8661e8621"

REDIS = BackendSpec(
    name="Redis",
    image=REDIS_IMAGE,
    port=REDIS_PORT,
    database=REDIS_DATABASE,
    user=REDIS_USER,
    password=REDIS_PASSWORD,
    environment=(),
    ready_command=(
        "redis-cli",
        "-h",
        "127.0.0.1",
        "-p",
        str(REDIS_PORT),
        "PING",
    ),
    schema_resource=None,
    schema_path=None,
    initialize_command=(
        "redis-cli",
        "-h",
        "127.0.0.1",
        "-p",
        str(REDIS_PORT),
        "SET",
        "conformance:bootstrap",
        "ready",
    ),
)


class Redis(DatabaseContainer):
    """Own a disposable Redis server."""

    def __init__(self) -> None:
        super().__init__(
            REDIS,
            container_factory=DockerContainer,
        )
