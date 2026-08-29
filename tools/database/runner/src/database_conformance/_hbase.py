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
HBASE_ZOOKEEPER_PORT = 2181
HBASE_MASTER_PORT = 16000
HBASE_REGIONSERVER_PORT = 16020
HBASE_1_IMAGE = "otel-conformance-hbase:1.7.2"
HBASE_2_IMAGE = "otel-conformance-hbase:2.4.18"
_HBASE_1_SHA512 = (
    "43c633606f4316319d0e872862bfee935a191308239ca42ad9545402fb9a83f9"
    "399845123bdcda60c315bcb09bd7555375b73afcb3d668453d56e3985bf284fa"
)
_HBASE_2_SHA512 = (
    "1d90aa46271d262abbebc6b807778353a71743be5c30491bec7ccafd05f2ecf8"
    "b3ff5c193addf28efd8d0cae4e1748ee74fdefd97fc8499cb1c163f5a2eed48d"
)


class HBase(DatabaseContainer):
    """Own an HBase fixture built from an Apache distribution."""

    def __init__(self, version: str, checksum: str) -> None:
        image_name = f"otel-conformance-hbase:{version}"
        image_context = Path(
            str(
                resources.files("database_conformance").joinpath("hbase-image")
            )
        )
        self._image = DockerImage(
            path=image_context,
            tag=image_name,
            clean_up=True,
            buildargs={
                "HBASE_VERSION": version,
                "HBASE_SHA512": checksum,
            },
        )
        super().__init__(
            BackendSpec(
                name=f"HBase {version}",
                image=image_name,
                port=HBASE_ZOOKEEPER_PORT,
                database=HBASE_DATABASE,
                user="",
                password="",
                environment=(),
                ready_command=(
                    "bash",
                    "-c",
                    "echo \"status 'simple'\" | hbase shell -n",
                ),
                schema_resource="hbase.rb",
                schema_path="/tmp/otel-conformance-hbase.rb",
                schema_command=(
                    "hbase",
                    "shell",
                    "-n",
                    "/tmp/otel-conformance-hbase.rb",
                ),
                hostname="localhost",
                fixed_ports=(
                    HBASE_ZOOKEEPER_PORT,
                    HBASE_MASTER_PORT,
                    HBASE_REGIONSERVER_PORT,
                ),
            ),
            container_factory=DockerContainer,
        )

    def start(self) -> HBase:
        try:
            self._image.build()
        except DockerException as error:
            self._image.remove()
            raise DatabaseBackendError(
                "Could not build the HBase fixture from the Apache HBase "
                f"distribution: {error}"
            ) from error
        return super().start()

    def close(self) -> None:
        try:
            super().close()
        finally:
            self._image.remove()


class HBase1(HBase):
    """Own an HBase fixture compatible with the 1.x client line."""

    def __init__(self) -> None:
        super().__init__("1.7.2", _HBASE_1_SHA512)


class HBase2(HBase):
    """Own an HBase fixture compatible with the 2.x client line."""

    def __init__(self) -> None:
        super().__init__("2.4.18", _HBASE_2_SHA512)
