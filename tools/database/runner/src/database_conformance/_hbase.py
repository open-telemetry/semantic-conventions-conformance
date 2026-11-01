# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Apache HBase local backend definitions."""

from __future__ import annotations

from importlib import resources
from pathlib import Path

from docker.errors import DockerException
from testcontainers.core.container import DockerContainer
from testcontainers.core.image import DockerImage

from ._container import BackendSpec, DatabaseBackendError, DatabaseContainer

HBASE_DATABASE = "conformance"
HBASE_MASTER_PORT = 16000
HBASE_REGIONSERVER_PORT = 16020
HBASE_VERSION = "3.0.0"
_HBASE_SHA512 = (
    "8290bc3cece084d36f7f47aae726268c7332e4828c6e8599df1343b03348e93f"
    "91165fad03ac6107bfbf0d8535e72024fa5d19217890d2848d013d8418a584ed"
)
HBASE_IMAGE = f"otel-conformance-hbase:{HBASE_VERSION}"


class HBase(DatabaseContainer):
    """Own an HBase fixture built from an Apache distribution."""

    def __init__(self) -> None:
        image_context = Path(
            str(
                resources.files("database_conformance").joinpath("hbase-image")
            )
        )
        self._image = DockerImage(
            path=image_context,
            tag=HBASE_IMAGE,
            clean_up=True,
            buildargs={
                "HBASE_VERSION": HBASE_VERSION,
                "HBASE_SHA512": _HBASE_SHA512,
            },
        )
        self._image_owned = False
        super().__init__(
            BackendSpec(
                name=f"HBase {HBASE_VERSION}",
                image=HBASE_IMAGE,
                port=HBASE_MASTER_PORT,
                database=HBASE_DATABASE,
                user="",
                password="",
                environment=(),
                ready_command=(
                    "bash",
                    "-c",
                    "echo \"status 'simple'\" | hbase shell -n",
                ),
                schema_copy=("hbase.rb", "/tmp/otel-conformance-hbase.rb"),
                initialize_command=(
                    "hbase",
                    "shell",
                    "-n",
                    "/tmp/otel-conformance-hbase.rb",
                ),
                hostname="localhost",
                fixed_ports=(
                    HBASE_MASTER_PORT,
                    HBASE_REGIONSERVER_PORT,
                ),
            ),
            container_factory=DockerContainer,
        )

    def start(self) -> HBase:
        if self._image_owned:
            raise DatabaseBackendError("HBase has already been started")
        self._image_owned = True
        try:
            try:
                self._image.build()
            except DockerException as error:
                raise DatabaseBackendError(
                    "Could not build the HBase fixture from the Apache HBase "
                    f"distribution: {error}"
                ) from error
            return super().start()
        except BaseException as error:
            try:
                self.close()
            except DockerException as cleanup_error:
                raise DatabaseBackendError(
                    f"{error}\nHBase fixture cleanup also failed: "
                    f"{cleanup_error}"
                ) from error
            raise

    def close(self) -> None:
        try:
            super().close()
        finally:
            if self._image_owned:
                self._image.remove()
                self._image_owned = False
