# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A session-scoped PostgreSQL backend managed through Docker."""

from __future__ import annotations

import logging
import re
import subprocess
import time
from importlib import resources
from types import TracebackType
from typing import Mapping

from opentelemetry.conformance._env import timeout_seconds

logger = logging.getLogger(__name__)

# renovate: datasource=docker depName=postgres versioning=docker
POSTGRES_IMAGE = "postgres:18.6-bookworm@sha256:1c59e2c3c818eaa0f0628f695b36e7c9e362d6b219b36a54a32df645cbd7e1af"

POSTGRES_HOST = "127.0.0.1"
POSTGRES_PORT = 5432
POSTGRES_DATABASE = "conformance"
POSTGRES_USER = "conformance"
POSTGRES_PASSWORD = "conformance"

_STARTUP_TIMEOUT = ("OTEL_CONFORMANCE_POSTGRES_STARTUP_TIMEOUT", 60.0)
_DOCKER_TIMEOUT = ("OTEL_CONFORMANCE_POSTGRES_DOCKER_TIMEOUT", 300.0)
_POLL_INTERVAL_SECONDS = 0.25
_CONTAINER_ID = re.compile(r"[0-9a-f]{12,64}")


class Postgres:
    """Own one PostgreSQL container and its initialized schema."""

    def __init__(self) -> None:
        self._container_id: str | None = None
        self._published_port: int | None = None

    @property
    def variables(self) -> Mapping[str, str]:
        """Language-neutral connection fields for scenario environments."""
        if self._published_port is None:
            raise RuntimeError("PostgreSQL has not been started")
        return {
            "POSTGRES_HOST": POSTGRES_HOST,
            "POSTGRES_PORT": str(self._published_port),
            "POSTGRES_DATABASE": POSTGRES_DATABASE,
            "POSTGRES_USER": POSTGRES_USER,
            "POSTGRES_PASSWORD": POSTGRES_PASSWORD,
        }

    def start(self) -> Postgres:
        """Start PostgreSQL, wait until it is ready, and apply the schema."""
        if self._container_id is not None:
            raise RuntimeError("PostgreSQL has already been started")

        result = self._docker(
            "run",
            "--detach",
            "--rm",
            "--publish",
            f"{POSTGRES_HOST}::{POSTGRES_PORT}",
            "--env",
            f"POSTGRES_DB={POSTGRES_DATABASE}",
            "--env",
            f"POSTGRES_USER={POSTGRES_USER}",
            "--env",
            f"POSTGRES_PASSWORD={POSTGRES_PASSWORD}",
            POSTGRES_IMAGE,
        )
        if result.returncode != 0:
            raise RuntimeError(self._failure("start PostgreSQL", result))

        container_id = result.stdout.strip()
        if not _CONTAINER_ID.fullmatch(container_id):
            message = (
                "Docker started PostgreSQL but returned an invalid container "
                f"id: {container_id!r}"
            )
            if container_id:
                self._container_id = container_id
                cleanup_error = self._remove()
                if cleanup_error is not None:
                    message += f"\nPostgreSQL cleanup also failed: {cleanup_error}"
            raise RuntimeError(message)
        self._container_id = container_id

        try:
            self._published_port = self._read_published_port()
            self._wait_until_ready()
            self._apply_schema()
        except BaseException as error:
            cleanup_error = self._remove()
            if cleanup_error is not None:
                raise RuntimeError(
                    f"{error}\nPostgreSQL cleanup also failed: {cleanup_error}"
                ) from error
            raise

        return self

    def _read_published_port(self) -> int:
        result = self._docker(
            "port", self._require_container(), f"{POSTGRES_PORT}/tcp"
        )
        if result.returncode != 0:
            raise RuntimeError(
                self._failure("read PostgreSQL's published port", result)
            )

        published = result.stdout.strip()
        host, separator, raw_port = published.rpartition(":")
        if (
            separator != ":"
            or host != POSTGRES_HOST
            or not raw_port.isdecimal()
            or not 0 < int(raw_port) <= 65535
        ):
            raise RuntimeError(
                "Docker returned an invalid PostgreSQL port mapping: "
                f"{published!r}"
            )
        return int(raw_port)

    def _wait_until_ready(self) -> None:
        startup = timeout_seconds(*_STARTUP_TIMEOUT)
        deadline = time.monotonic() + startup
        while time.monotonic() < deadline:
            state = self._docker(
                "inspect",
                "--format",
                "{{.State.Running}}",
                self._require_container(),
            )
            if state.returncode != 0:
                raise RuntimeError(
                    self._with_logs(
                        self._failure("inspect PostgreSQL", state)
                    )
                )
            if state.stdout.strip() != "true":
                raise RuntimeError(
                    self._with_logs(
                        "PostgreSQL stopped before it became ready"
                    )
                )

            ready = self._docker(
                "exec",
                self._require_container(),
                "pg_isready",
                "--host",
                POSTGRES_HOST,
                "--port",
                str(POSTGRES_PORT),
                "--username",
                POSTGRES_USER,
                "--dbname",
                POSTGRES_DATABASE,
            )
            if ready.returncode == 0:
                return
            time.sleep(_POLL_INTERVAL_SECONDS)

        raise RuntimeError(
            self._with_logs(
                f"PostgreSQL did not become ready within {startup}s"
            )
        )

    def _apply_schema(self) -> None:
        schema = (
            resources.files("database_conformance")
            .joinpath("postgres.sql")
            .read_text(encoding="utf-8")
        )
        result = self._docker(
            "exec",
            "--interactive",
            "--env",
            f"PGPASSWORD={POSTGRES_PASSWORD}",
            self._require_container(),
            "psql",
            "--no-psqlrc",
            "--set",
            "ON_ERROR_STOP=1",
            "--host",
            POSTGRES_HOST,
            "--port",
            str(POSTGRES_PORT),
            "--username",
            POSTGRES_USER,
            "--dbname",
            POSTGRES_DATABASE,
            "--file",
            "-",
            stdin=schema,
        )
        if result.returncode != 0:
            raise RuntimeError(
                self._with_logs(
                    self._failure("apply the PostgreSQL schema", result)
                )
            )

    def _with_logs(self, message: str) -> str:
        result = self._docker("logs", self._require_container())
        output = (result.stdout + result.stderr).strip()
        if result.returncode != 0:
            output = self._failure("read PostgreSQL logs", result)
        return f"{message}\n--- PostgreSQL logs ---\n{output}"

    def _require_container(self) -> str:
        if self._container_id is None:
            raise RuntimeError("PostgreSQL has not been started")
        return self._container_id

    def _docker(
        self, *arguments: str, stdin: str | None = None
    ) -> subprocess.CompletedProcess[str]:
        command = ["docker", *arguments]
        try:
            return subprocess.run(  # noqa: S603
                command,
                input=stdin,
                capture_output=True,
                text=True,
                timeout=timeout_seconds(*_DOCKER_TIMEOUT),
                check=False,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                "Docker is required for database conformance runs but the "
                "docker command was not found"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"Docker command timed out: {' '.join(command)}"
            ) from error
        except OSError as error:
            raise RuntimeError(
                f"Docker command could not be started: {error}"
            ) from error

    @staticmethod
    def _failure(
        operation: str, result: subprocess.CompletedProcess[str]
    ) -> str:
        output = (result.stdout + result.stderr).strip()
        return (
            f"Could not {operation}; Docker exited with "
            f"{result.returncode}\n{output}"
        )

    def _remove(self) -> str | None:
        container_id = self._container_id
        if container_id is None:
            return None
        try:
            result = self._docker("rm", "--force", container_id)
        except RuntimeError as error:
            return str(error)
        if result.returncode != 0:
            return self._failure("remove PostgreSQL", result)
        self._container_id = None
        self._published_port = None
        return None

    def close(self) -> None:
        """Remove PostgreSQL if it was started."""
        error = self._remove()
        if error is not None:
            raise RuntimeError(error)

    def __enter__(self) -> Postgres:
        return self.start()

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        self.close()
