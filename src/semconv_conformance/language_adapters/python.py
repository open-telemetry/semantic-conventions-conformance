# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Python scenario adapter."""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path

from ._common import (
    AdapterContext,
    CommandResult,
    LanguageAdapter,
    data_file_list_scenarios,
    noop_prebuild,
    uv_cmd,
)

logger = logging.getLogger(__name__)


def _python_executable_for_env(env_dir: Path) -> Path:
    if sys.platform == "win32":
        return env_dir / "Scripts" / "python.exe"
    return env_dir / "bin" / "python"


def _scenario_env_dir(domain_dir: Path, lib: str, ecosystem: str) -> Path:
    return domain_dir / ".cache" / "python-test-envs" / f"{lib}-{ecosystem}"


def install_with_uv_for_python(
    domain_dir: Path,
    python_executable: Path | str,
    *install_args: str,
    label: str,
) -> None:
    logger.info("=== Installing %s ===", label)
    subprocess.run(
        [uv_cmd(), "pip", "install", "--python", str(python_executable), *install_args],
        cwd=domain_dir,
        check=True,
    )


def install_with_uv(domain_dir: Path, *install_args: str, label: str) -> None:
    install_with_uv_for_python(domain_dir, sys.executable, *install_args, label=label)


def _ensure_env(ctx: AdapterContext, lib: str, ecosystem: str) -> Path:
    env_dir = _scenario_env_dir(ctx.domain_dir, lib, ecosystem)
    python_executable = _python_executable_for_env(env_dir)
    if not python_executable.is_file():
        logger.info("=== Creating isolated Python env: %s ===", env_dir)
        env_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [uv_cmd(), "venv", "--python", sys.executable, str(env_dir)],
            cwd=ctx.domain_dir,
            check=True,
        )

    install_with_uv_for_python(
        ctx.domain_dir,
        python_executable,
        "-e",
        "python/shared",
        label=f"shared Python test support in {env_dir.name}",
    )
    lock_file = f"python/{lib}/requirements-{ecosystem}.lock"
    req_file = lock_file if (ctx.domain_dir / lock_file).is_file() else f"python/{lib}/requirements-{ecosystem}.txt"
    install_with_uv_for_python(
        ctx.domain_dir,
        python_executable,
        "-r",
        req_file,
        label=f"Python test dependencies for {lib}/{ecosystem} in {env_dir.name}",
    )
    return python_executable


def build_adapter(ctx: AdapterContext) -> LanguageAdapter:
    def install(lib: str, ecosystem: str) -> None:
        _ensure_env(ctx, lib, ecosystem)

    def run(lib: str, ecosystem: str, env: dict[str, str]) -> CommandResult:
        scenario_file = ctx.domain_dir / "python" / lib / f"run_{ecosystem}.py"
        if not scenario_file.is_file():
            return CommandResult(False, 0)
        python_executable = _python_executable_for_env(_scenario_env_dir(ctx.domain_dir, lib, ecosystem))
        if not python_executable.is_file():
            python_executable = _ensure_env(ctx, lib, ecosystem)
        proc = subprocess.run([str(python_executable), str(scenario_file)], env=env)
        return CommandResult(True, proc.returncode)

    def list_scenarios() -> list[str]:
        return data_file_list_scenarios(ctx.domain_dir, "python")

    return LanguageAdapter(
        install_dependencies=install,
        prebuild_scenario=noop_prebuild,
        run_scenario=run,
        list_scenarios=list_scenarios,
    )
