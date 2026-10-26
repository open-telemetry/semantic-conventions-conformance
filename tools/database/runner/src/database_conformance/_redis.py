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
REDIS_IMAGE = "redis:8.4.0-bookworm@sha256:c22af04bb576503bf16b3e34a1fd2fd82de0f765afd866d2e380145e0af30d78"

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
        "-e",
        "-h",
        "127.0.0.1",
        "-p",
        str(REDIS_PORT),
        "PING",
    ),
    schema_copy=None,
    initialize_command=None,
)


class Redis(DatabaseContainer):
    """Own a disposable Redis server."""

    def __init__(self) -> None:
        super().__init__(
            REDIS,
            container_factory=DockerContainer,
        )
