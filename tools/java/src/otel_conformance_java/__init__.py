# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""``otel-conformance-java``: builds and runs a JVM conformance scenario.

Every Java scenario is prepared and started the same way — sync the resolved
classpath into the build's ``build/scenario-runtime``, then run a plain
``java`` process against it — so the toolchain lives here rather than being
restated in each ``conformance.yaml``. A scenario directory names its Gradle
project and main class, and opts into agent attachment when needed; nothing
else about Java appears in the file.

Two subcommands, matching the two phases a package has:

``prepare``
    What a package's ``setup:`` runs. Invokes the committed Gradle wrapper's
    ``prepareRuntime`` for the library.

``run``
    What a scenario's ``run:`` runs. Executes ``java`` directly rather than
    through Gradle, so the scenario inherits the fresh OTLP endpoint the
    runner injected instead of whatever a long-lived Gradle daemon started
    with.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from typing import Sequence

# The file that marks the root of a language's build. Searched for upwards
# from the scenario directory, so a scenario says nothing about how deep it is
# nested — the layout can change without touching every conformance.yaml.
BUILD_MARKER = "settings.gradle.kts"

# Where `prepareRuntime` puts what it syncs, relative to the build root. Under
# the root rather than under each project, so where a Gradle project sits on
# disk is the build's business rather than something restated here.
RUNTIME = Path("build") / "scenario-runtime"

AGENT_JAR = "opentelemetry-javaagent.jar"
AGENT_EXTENSION_JAR = "conformance-javaagent-extension.jar"


class LayoutError(RuntimeError):
    """The Java build could not be found from where this was run."""


def build_root(start: Path | None = None) -> Path:
    """The directory holding :data:`BUILD_MARKER`, at or above ``start``."""
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / BUILD_MARKER).is_file():
            return candidate
    raise LayoutError(
        f"no {BUILD_MARKER} at or above {here} — `otel-conformance-java` runs "
        "from a scenario directory inside a Java conformance build"
    )


def gradle_command(root: Path, task: str) -> list[str]:
    """The Gradle wrapper invocation for ``task``.

    The wrapper's main class rather than ``gradlew``/``gradlew.bat``: the
    runner executes argv directly, so there is no shell to pick the right
    script for the platform.
    """
    return [
        _java(),
        "-Dorg.gradle.appname=gradlew",
        "-classpath",
        str(root / "gradle" / "wrapper" / "gradle-wrapper.jar"),
        "org.gradle.wrapper.GradleWrapperMain",
        "--project-dir",
        str(root),
        task,
    ]


def java_command(
    root: Path,
    project: str,
    main_class: str,
    *,
    agent: bool,
    arguments: Sequence[str] = (),
) -> list[str]:
    """The ``java`` invocation for one scenario."""
    # A path, not a name: two libraries can both have a `javaagent` project,
    # and `prepareRuntime` flattens the same way.
    runtime = root / RUNTIME / project.strip(":").replace(":", "-")
    command = [_java()]
    if agent:
        agent_jar = runtime / "agent" / AGENT_JAR
        extension_jar = runtime / "agent" / AGENT_EXTENSION_JAR
        command += [
            f"-Dotel.javaagent.extensions={extension_jar}",
            f"-javaagent:{agent_jar}",
        ]
    # A wildcard entry, expanded by the JVM itself: the set of jars is
    # whatever the library resolved, which is not known here.
    command += ["-classpath", str(runtime / "lib" / "*"), main_class]
    command += list(arguments)
    return command


def _java() -> str:
    """The JVM to use, preferring ``JAVA_HOME`` over whatever is on PATH."""
    home = os.environ.get("JAVA_HOME")
    if home:
        for name in ("java", "java.exe"):
            candidate = Path(home) / "bin" / name
            if candidate.is_file():
                return str(candidate)
    return "java"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="otel-conformance-java",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subcommands = parser.add_subparsers(dest="command", required=True)

    prepare = subcommands.add_parser(
        "prepare", help="build a Gradle project's scenario runtime"
    )
    prepare.add_argument(
        "project",
        help="the Gradle project to prepare, e.g. armeria:opentelemetry-library",
    )

    run = subcommands.add_parser("run", help="run a scenario's main class")
    run.add_argument("project", help="the Gradle project that was prepared")
    run.add_argument("main_class", help="the scenario's main class")
    run.add_argument(
        "--agent",
        action="store_true",
        help="attach the Java agent from the prepared runtime",
    )
    run.add_argument(
        "arguments",
        nargs=argparse.REMAINDER,
        help="arguments passed to the scenario, verbatim",
    )

    arguments = parser.parse_args(argv)
    root = build_root()

    if arguments.command == "prepare":
        project = arguments.project.strip(":")
        command = gradle_command(root, f":{project}:prepareRuntime")
    else:
        command = java_command(
            root,
            arguments.project,
            arguments.main_class,
            agent=arguments.agent,
            arguments=arguments.arguments,
        )

    return subprocess.call(command)  # noqa: S603


if __name__ == "__main__":
    sys.exit(main())
