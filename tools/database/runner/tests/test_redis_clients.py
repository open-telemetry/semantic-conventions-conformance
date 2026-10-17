# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Real Redis connections from prepared Java scenario runtimes."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import docker
import pytest
from docker.errors import DockerException
from testcontainers.core.container import ExecConfig

from database_conformance._redis import Redis
from opentelemetry.conformance._env import build_env

_JAVA_ROOT = Path(__file__).parents[4] / "scenarios" / "database" / "java"


@pytest.fixture(
    scope="module",
    params=[
        ("jedis", "opentelemetry-javaagent", "JedisJavaagentScenario"),
        ("lettuce", "opentelemetry-javaagent", "LettuceJavaagentScenario"),
        ("lettuce", "opentelemetry-library", "LettuceLibraryScenario"),
        ("rediscala", "opentelemetry-javaagent", "RediscalaJavaagentScenario"),
        ("redisson", "opentelemetry-javaagent", "RedissonJavaagentScenario"),
    ],
    ids=["jedis", "lettuce-agent", "lettuce-library", "rediscala", "redisson"],
)
def launcher(request: pytest.FixtureRequest) -> tuple[str, Path, str]:
    client, instrumentation, main_class = request.param
    runtime = (
        _JAVA_ROOT
        / "build"
        / "scenario-runtime"
        / f"shared-redis-{client}-{instrumentation}"
    )
    if not (runtime / "lib").is_dir():
        pytest.skip(f"prepare shared:redis:{client}:{instrumentation} first")
    java = shutil.which("java")
    if java is None:
        pytest.skip("Java is not installed")
    try:
        with_client = docker.from_env()
        try:
            with_client.ping()
        finally:
            with_client.close()
    except DockerException as error:
        pytest.skip(f"Docker is not available: {error}")
    return java, runtime, main_class


@pytest.mark.parametrize(
    ("database", "user", "password"),
    [
        ("0", "default", ""),
        ("3", "default", ""),
        ("3", "conformance", " test password "),
    ],
    ids=["defaults", "database", "database-and-auth"],
)
def test_redis_clients_use_runner_connection_fields(
    launcher: tuple[str, Path, str],
    database: str,
    user: str,
    password: str,
) -> None:
    java, runtime, main_class = launcher
    with Redis() as backend:
        container = backend._container
        assert container is not None
        if password:
            result = container.exec(
                ExecConfig(
                    command=[
                        "redis-cli",
                        "ACL",
                        "SETUSER",
                        user,
                        "on",
                        f">{password}",
                        "~*",
                        "+@all",
                    ]
                )
            )
            assert result.exit_code == 0 and result.output.strip() == b"OK"
            result = container.exec(
                ExecConfig(
                    command=["redis-cli", "ACL", "SETUSER", "default", "off"]
                )
            )
            assert result.exit_code == 0 and result.output.strip() == b"OK"

        env = build_env(
            injected={
                **backend.variables,
                "DATABASE_NAME": database,
                "DATABASE_USER": user,
                "DATABASE_PASSWORD": password,
                "OTEL_EXPORTER_OTLP_ENDPOINT": "http://127.0.0.1:9",
                "OTEL_TRACES_EXPORTER": "none",
                "OTEL_METRICS_EXPORTER": "none",
                "OTEL_LOGS_EXPORTER": "none",
            }
        )
        env["JAVA_HOME"] = str(Path(java).parent.parent)
        result = subprocess.run(
            [
                java,
                "-cp",
                str(runtime / "lib" / "*"),
                "io.opentelemetry.conformance.scenario.ScenarioLauncher",
                main_class,
                "set_get",
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=45,
            check=False,
            creationflags=subprocess.CREATE_NO_WINDOW
            if os.name == "nt"
            else 0,
        )
        assert result.returncode == 0, result.stdout + result.stderr

        credentials = (
            ["--no-auth-warning", "--user", user, "-a", password]
            if password
            else []
        )
        for selected in (database, "1"):
            result = container.exec(
                ExecConfig(
                    command=[
                        "redis-cli",
                        *credentials,
                        "-n",
                        selected,
                        "GET",
                        "conformance:value",
                    ]
                )
            )
            assert result.exit_code == 0
            assert result.output.strip() == (
                b"value" if selected == database else b""
            )
