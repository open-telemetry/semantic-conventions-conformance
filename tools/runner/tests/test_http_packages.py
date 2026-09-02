# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

import pytest
import yaml

from opentelemetry.conformance import WeaverSpec, load_spec
from opentelemetry.conformance import _session as session_module
from opentelemetry.conformance._env import action_table_json
from opentelemetry.conformance._otlp_capture import (
    CapturedExport,
    CapturedWindow,
    CaptureSnapshot,
    CaptureWindow,
    decode_window,
)
from opentelemetry.conformance._session import ConformanceSession

ROOT = Path(__file__).resolve().parents[3]
CONTRACT = ROOT / "tools" / "http" / "test-client" / "contract.yaml"
CONTRACT_REFERENCE = "../../../../../../tools/http/test-client/contract.yaml"

# A measured server that answers only what the runner's table describes, and
# writes that table down so a test can read what it was given. Deliberately
# free of the shared helpers: the point is what arrived in the environment.
_MEASURED_SERVER = """
import json
import os
import sys
import threading
from wsgiref.simple_server import WSGIRequestHandler, make_server

TABLE = json.loads(os.environ["OTEL_CONFORMANCE_SCENARIO_ACTIONS"])
ANSWERS = {
    (entry["request"]["method"], entry["request"]["path"]): entry["response"]
    for entry in TABLE
}


def app(environ, start_response):
    answer = ANSWERS.get(
        (environ["REQUEST_METHOD"], environ["PATH_INFO"])
    )
    if answer is None:
        body = b'{"message": "no such route"}'
        start_response(
            "404 Not Found",
            [
                ("Content-Type", "application/json"),
                ("Content-Length", str(len(body))),
            ],
        )
        return [body]
    body = answer["body"].encode()
    start_response(
        f"{answer['status']} Status",
        [
            ("Content-Type", "application/json"),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


class Quiet(WSGIRequestHandler):
    def log_message(self, *_args):
        pass


server = make_server(
    "127.0.0.1",
    int(os.environ["OTEL_HTTP_SCENARIO_PORT"]),
    app,
    handler_class=Quiet,
)
threading.Thread(target=server.serve_forever, daemon=True).start()
sys.stdin.read()
server.shutdown()
open(sys.argv[1], "w", encoding="utf-8").write(json.dumps(TABLE))
"""

# Nothing the shared contract describes: every route, status and body differs,
# so a driver answering from its own installed copy cannot pass. It declares
# only the runner-driven side, which is what makes this package persistent.
_CUSTOM_CONTRACT = """
variants:
  measured-server:
    description: The runner drives the instrumented server from outside.
    driver: runner

readiness:
  description: Checks whether the custom server is ready.
  action:
    request:
      method: GET
      path: /custom/ready
    response:
      status: 200
      body: '{"ready": true}'

scenarios:
  - description: Sends a request to the custom route.
    action:
      request:
        method: POST
        path: /custom/first
        body: '{"first": true}'
      response:
        status: 201
        body: '{"created": 1}'
    expect:
      measured-server:
        spans: []
        metrics: []
        events: []

  - description: Sends a request to the other custom route.
    action:
      request:
        method: GET
        path: /custom/second
      response:
        status: 202
        body: '{"accepted": 2}'
    expect:
      measured-server:
        spans: []
        metrics: []
        events: []
"""


def declared_packages() -> list[Path]:
    """Every HTTP package the repository declares, and nothing else.

    Read from the index rather than the working tree, which is what the
    workflow that builds the scenario matrix does. A checkout that has
    installed a workspace holds symlinked copies of these same files, and
    walking into those would count a package more than once.
    """
    listed = subprocess.run(
        ["git", "ls-files", "-z", "scenarios/http/**/conformance.yaml"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sorted(
        ROOT / relative for relative in listed.split("\0") if relative
    )


def _keys(document: object) -> set[str]:
    """Every mapping key anywhere in a parsed document."""
    if isinstance(document, dict):
        mapping = cast("dict[str, object]", document)
        return set(mapping) | {
            key for value in mapping.values() for key in _keys(value)
        }
    if isinstance(document, list):
        return {
            key
            for value in cast("list[object]", document)
            for key in _keys(value)
        }
    return set()


def test_all_http_packages_use_the_contract_execution_model() -> None:
    declarations = declared_packages()
    clients = [path for path in declarations if path.parent.name == "client"]
    servers = [path for path in declarations if path.parent.name == "server"]

    assert len(declarations) == 50
    assert len(clients) == 23
    assert len(servers) == 27

    contract = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    scenario_count = len(contract["scenarios"])
    roles = {
        name: variant["driver"]
        for name, variant in contract["variants"].items()
    }
    # One catalog of actions, two execution roles over it.
    assert roles == {"client": "instrumentation", "server": "runner"}
    assert all(
        set(entry["expect"]) == set(roles) for entry in contract["scenarios"]
    )

    for path in declarations:
        package_directory = path.parent
        side = package_directory.name
        document = yaml.safe_load(path.read_text(encoding="utf-8"))

        assert document["scenario_contract"] == CONTRACT_REFERENCE, path
        assert (package_directory / document["scenario_contract"]).resolve() == CONTRACT
        assert document["scenario_contract_variant"] == side, path
        assert document["scenario_contract_variant"] in roles, path
        assert "scenarios" not in document, path

        package = load_spec(package_directory)
        assert len(package.scenarios) == scenario_count, path
        assert len(package.action_table) == scenario_count + 1, path

        # The lifecycle follows from the variant's driver role, so no package
        # names the internal protocol the runner and a driven process speak,
        # nor asks the driver for it on the command line.
        assert "protocol" not in _keys(document), path
        assert not isinstance(document["scenario_run"], dict), path
        assert "--persistent" not in document["scenario_run"], path
        protocols = {scenario.protocol for scenario in package.scenarios.values()}
        if side == "client":
            assert protocols == {None}, path
        else:
            assert document["scenario_run"].startswith(
                "otel-http-drive --serve "
            ), path
            assert protocols == {"jsonl-v1"}, path

        command = next(iter(package.scenarios.values())).run
        for token in command:
            if token.endswith((".py", ".js")):
                assert (package_directory / token).is_file(), (path, token)


class _StubWeaver:
    """Weaver, reduced to what a persistent batch touches."""

    otlp_endpoint = "http://weaver"

    def start(self) -> "_StubWeaver":
        return self

    def end(self, timeout: int) -> object:
        del timeout
        raise AssertionError("this test does not finalize the package")

    def close(self) -> None:
        pass


class _StubCapture:
    """A capture that records nothing, so only the driver is under test."""

    def __init__(self, upstream_endpoint: str) -> None:
        del upstream_endpoint
        self.endpoint = "http://capture"

    def __enter__(self) -> "_StubCapture":
        return self

    def __exit__(self, *_args: object) -> None:
        pass

    def open_window(self, name: str) -> CaptureWindow:
        return CaptureWindow(name, 1)

    def set_change_notifier(self, notifier: object) -> None:
        del notifier

    def snapshot(self, window: CaptureWindow) -> CaptureSnapshot:
        del window
        return CaptureSnapshot((), 0)

    def drain(self, *, timeout: float | None = None) -> None:
        del timeout

    def close_window(
        self, window: CaptureWindow, *, timeout: float | None = None
    ) -> CapturedWindow:
        del timeout
        return decode_window(window, ())

    def requests(self, window: CaptureWindow) -> tuple[CapturedExport, ...]:
        del window
        return ()


def test_a_custom_contract_reaches_the_measured_server(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The runner owns the table, and the driver hands it on untouched.

    A package may point at a contract of its own, so a driver that rebuilt the
    table from whichever contract its own installation shipped would drive one
    contract while the package was judged against another.

    The command asks for no lifecycle. That the driver runs persistently at
    all is the runner telling it so, from the variant's driver role.
    """
    pytest.importorskip("otel_http_test_client")

    package = tmp_path / "package"
    package.mkdir()
    (package / "contract.yaml").write_text(_CUSTOM_CONTRACT, encoding="utf-8")
    server = package / "server.py"
    server.write_text(_MEASURED_SERVER, encoding="utf-8")
    received = tmp_path / "received.json"
    (package / "conformance.yaml").write_text(
        yaml.safe_dump(
            {
                "instrumented_library": "custom",
                "instrumentation_library": "custom-instrumentation",
                "scenario_contract": "contract.yaml",
                "scenario_contract_variant": "measured-server",
                "scenario_run": [
                    sys.executable,
                    "-m",
                    "otel_http_test_client",
                    "--serve",
                    sys.executable,
                    str(server),
                    str(received),
                ],
            }
        ),
        encoding="utf-8",
    )

    spec = load_spec(package)
    monkeypatch.setattr(
        ConformanceSession, "_new_live_check", lambda _self: _StubWeaver()
    )
    monkeypatch.setattr(session_module, "OtlpCaptureProxy", _StubCapture)
    monkeypatch.setenv("OTEL_CONFORMANCE_SCENARIO_WINDOW_TIMEOUT", "60")
    monkeypatch.setenv("OTEL_CONFORMANCE_SCENARIO_SETTLE_DELAY", "0.01")
    opened = ConformanceSession(
        spec,
        tmp_path / "reports",
        variables={},
        weaver=WeaverSpec(registry="model"),
        env={},
        data_file=tmp_path / "data.json",
        build_data=lambda *_args: {},
    )

    reports = opened._run_persistent(tuple(spec.scenarios.values()))  # pyright: ignore[reportPrivateUsage]

    assert [report.failures for report in reports] == [[], []]
    # Character for character what the runner parsed, and nothing the driver's
    # own installed contract would have produced.
    assert received.read_text(encoding="utf-8") == json.dumps(
        json.loads(action_table_json(spec.action_table))
    )
    assert [
        entry["request"]["path"] for entry in json.loads(received.read_text())
    ] == ["/custom/ready", "/custom/first", "/custom/second"]
