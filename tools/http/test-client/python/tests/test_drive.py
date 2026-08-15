# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The driver: what it sends, and how it starts and stops a scenario."""

from __future__ import annotations

import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

import otel_http_test_client.__main__ as driver
from otel_http_test_client import (
    CONTRACT,
    EXCHANGES,
    PORT_VARIABLE,
    REQUESTS,
    ContractError,
    Exchange,
    respond,
    verify,
    wait_for_health,
    wait_for_port,
)
from otel_http_test_client.__main__ import main

# A server scenario, in the language these tools are written in: bind the port
# the driver chose, answer the shared exchanges, stop when standard input
# closes. Written out rather than imported so the test drives a real process,
# which is the whole point of the arrangement.
_SCENARIO = """
import json
import sys

from otel_http_test_client import CONTENT_TYPE, respond, serve

SEEN = []


def app(environ, start_response):
    path = environ["PATH_INFO"]
    method = environ["REQUEST_METHOD"]
    query = environ.get("QUERY_STRING", "")
    SEEN.append(f"{method} {path}" + (f"?{query}" if query else ""))

    length = int(environ.get("CONTENT_LENGTH") or 0)
    request_body = environ["wsgi.input"].read(length).decode() or None
    status, text = respond(method, path, request_body)
    body = MANGLE(text).encode()

    start_response(
        f"{status} Status",
        [
            ("Content-Type", CONTENT_TYPE),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


serve(lambda: app)
print(json.dumps(SEEN), file=sys.stderr)
sys.exit(EXIT_CODE)
"""

# A scenario command that is a launcher rather than the server itself, which
# is the shape of every Java scenario: ``otel-conformance-java run ...`` starts
# the JVM and waits for it, so the process the driver started is not the
# process that has to stop.
_LAUNCHER = """
import subprocess
import sys

sys.exit(subprocess.call([sys.executable, *sys.argv[1:]]))
"""

# Behind that launcher, a server that answers but never stops on EOF, so the
# driver has to kill it. It writes down the port it holds, which is how a test
# sees whether it outlived the command that started it.
_DEAF_SERVER = """
import sys
from wsgiref.simple_server import make_server

from otel_http_test_client import CONTENT_TYPE, respond, scenario_port


def app(environ, start_response):
    length = int(environ.get("CONTENT_LENGTH") or 0)
    request_body = environ["wsgi.input"].read(length).decode() or None
    status, text = respond(
        environ["REQUEST_METHOD"], environ["PATH_INFO"], request_body
    )
    body = text.encode()
    start_response(
        f"{status} Status",
        [
            ("Content-Type", CONTENT_TYPE),
            ("Content-Length", str(len(body))),
        ],
    )
    return [body]


server = make_server("127.0.0.1", scenario_port(), app)
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(str(scenario_port()))
server.serve_forever()
"""

# Behind that launcher, a server that never binds the port the driver chose,
# which is what a JVM stuck on the way up looks like from the outside. It
# accepts, so a test connecting to it is answered for as long as it lives.
_DEAF_STARTER = """
import socket
import sys

listener = socket.socket()
listener.bind(("127.0.0.1", 0))
listener.listen(8)
with open(sys.argv[1], "w", encoding="utf-8") as handle:
    handle.write(str(listener.getsockname()[1]))
while True:
    listener.accept()[0].close()
"""


def _scenario(
    tmp_path: Path,
    source: str = _SCENARIO,
    *,
    exits: int = 0,
    mangle: str = "str",
) -> Path:
    """Write a scenario process out.

    ``mangle`` wraps each response body, so a test can make the scenario
    answer something the contract does not describe.
    """
    path = tmp_path / "scenario.py"
    path.write_text(
        source.replace("EXIT_CODE", str(exits)).replace("MANGLE", mangle),
        encoding="utf-8",
    )
    return path


def _drive(scenario: Path) -> subprocess.CompletedProcess[str]:
    """Run the driver as its own process, which is how the runner runs it."""
    return subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "otel_http_test_client",
            "--serve",
            sys.executable,
            str(scenario),
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
    )


def _launched(tmp_path: Path, source: str) -> list[str]:
    """A scenario command whose real server is its child, not itself."""
    launcher = tmp_path / "launcher.py"
    launcher.write_text(_LAUNCHER, encoding="utf-8")
    server = tmp_path / "deaf.py"
    server.write_text(source, encoding="utf-8")
    return [
        sys.executable,
        str(launcher),
        str(server),
        str(tmp_path / "port"),
    ]


def _stopped_answering(port_file: Path, timeout: float = 30.0) -> bool:
    """Whether the server behind the launcher let go of the port it held."""
    deadline = time.monotonic() + timeout
    while not port_file.exists():
        if time.monotonic() > deadline:
            pytest.fail("the server behind the launcher never started")
        time.sleep(0.1)

    port = int(port_file.read_text(encoding="utf-8"))
    while time.monotonic() < deadline:
        try:
            socket.create_connection(("127.0.0.1", port), timeout=1.0).close()
        except OSError:
            return True
        time.sleep(0.1)
    return False


class TestTheContract:
    def test_it_is_read_from_the_shared_file(self) -> None:
        assert CONTRACT.name == "contract.json"
        declared = json.loads(CONTRACT.read_text(encoding="utf-8"))
        assert len(EXCHANGES) == len(declared["requests"])
        assert len(REQUESTS) == len(EXCHANGES) - 1

    def test_every_request_says_what_it_is_for(self) -> None:
        assert all(exchange.why for exchange in EXCHANGES)

    def test_it_covers_both_error_classes(self) -> None:
        paths = [request.path for request in REQUESTS]
        assert "/status/404" in paths
        assert "/status/500" in paths

    def test_every_measured_request_has_an_answer(self) -> None:
        """Otherwise a scenario would be asked for traffic nothing defines."""
        for exchange in REQUESTS:
            status, body = respond(
                exchange.method, exchange.path, exchange.body
            )
            verify(exchange, status, body)

    def test_request_body_is_the_only_response_placeholder(self) -> None:
        placeholders = re.findall(
            r"\$\{[^}]+}", CONTRACT.read_text(encoding="utf-8")
        )

        assert placeholders
        assert set(placeholders) == {"${requestBody}"}


class TestAnsweringTheExchanges:
    def test_a_path_parameter_reaches_the_response(self) -> None:
        status, body = respond("GET", "/users/123")

        assert status == 200
        assert json.loads(body)["id"] == 123

    def test_one_path_shape_answers_both_error_statuses(self) -> None:
        assert respond("GET", "/status/404")[0] == 404
        assert respond("GET", "/status/500")[0] == 500

    def test_a_request_body_reaches_the_response(self) -> None:
        status, body = respond("POST", "/items", '{"name": "widget"}')

        assert status == 201
        assert json.loads(body)["payload"] == {"name": "widget"}

    def test_a_query_string_does_not_change_the_route(self) -> None:
        assert respond("GET", "/users/123?fields=other")[0] == 200

    def test_an_unknown_route_is_a_404(self) -> None:
        assert respond("GET", "/nothing/here")[0] == 404

    def test_the_method_is_part_of_the_route(self) -> None:
        assert respond("GET", "/items")[0] == 404


class TestVerifyingAnAnswer:
    """What keeps eleven languages' answers the same."""

    def _answer(self, exchange: Exchange) -> tuple[int, str]:
        status, response = respond(
            exchange.method, exchange.path, exchange.body
        )
        return status, response

    def test_a_contract_answer_passes(self) -> None:
        for exchange in REQUESTS:
            verify(exchange, *self._answer(exchange))

    def test_a_wrong_status_is_rejected(self) -> None:
        exchange = next(
            exchange for exchange in REQUESTS if exchange.path == "/status/404"
        )
        _status, response = self._answer(exchange)

        with pytest.raises(ContractError, match="answers 404"):
            verify(exchange, 200, response)

    def test_a_wrong_body_is_rejected(self) -> None:
        exchange = next(
            exchange for exchange in REQUESTS if exchange.path == "/users/123"
        )
        status, _response = self._answer(exchange)

        with pytest.raises(ContractError, match="answers"):
            verify(exchange, status, '{"id": "456"}')

    def test_formatting_is_not_part_of_the_contract(self) -> None:
        """Key order and whitespace are each language's JSON writer's call."""
        exchange = next(
            exchange for exchange in REQUESTS if exchange.path == "/items"
        )
        status, response = self._answer(exchange)
        reformatted = json.dumps(
            dict(reversed(list(json.loads(response).items()))), indent=4
        )

        verify(exchange, status, reformatted)

    def test_an_answer_that_is_not_json_is_rejected(self) -> None:
        exchange = next(
            exchange for exchange in EXCHANGES if exchange.readiness
        )
        status, _response = self._answer(exchange)

        with pytest.raises(ContractError, match="not the JSON"):
            verify(exchange, status, "<html>oops</html>")


class TestDrivingAServerScenario:
    def test_port_wait_uses_its_timeout_as_the_connection_budget(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        connection_timeouts: list[float] = []

        class Connection:
            def __enter__(self) -> None:
                return None

            def __exit__(self, *_args: object) -> None:
                return None

        def connect(
            _address: tuple[str, int], *, timeout: float
        ) -> Connection:
            connection_timeouts.append(timeout)
            return Connection()

        times = iter((100.0, 100.0))
        monkeypatch.setattr(
            "otel_http_test_client.time.monotonic", lambda: next(times)
        )
        monkeypatch.setattr(
            "otel_http_test_client.socket.create_connection", connect
        )

        assert wait_for_port(1234, timeout=0.1)
        assert connection_timeouts == [pytest.approx(0.1)]

    def test_port_binding_at_the_deadline_reports_startup_timeout(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        times = iter((0.0, 0.0, 60.0))
        monkeypatch.setattr(driver.time, "monotonic", lambda: next(times))
        monkeypatch.setattr(
            driver, "wait_for_port", lambda *_args, **_kwargs: True
        )

        def unexpected_health_check(*_args: object, **_kwargs: object) -> None:
            pytest.fail("health check received a non-positive timeout")

        monkeypatch.setattr(driver, "wait_for_health", unexpected_health_check)

        with pytest.raises(RuntimeError, match="did not listen"):
            driver._wait_for_start(
                object(), 1234, "http://127.0.0.1:1234", ["scenario"]
            )

    def test_it_sends_the_contract_in_order(self, tmp_path: Path) -> None:
        completed = _drive(_scenario(tmp_path))

        assert completed.returncode == 0, completed.stderr
        seen = json.loads(completed.stderr.strip().splitlines()[-1])
        assert [entry for entry in seen if entry != "GET /health"] == [
            f"{request.method} {request.path}" for request in REQUESTS
        ]

    def test_it_only_asks_whether_the_server_is_up_once(
        self, tmp_path: Path
    ) -> None:
        """Readiness polling would be telemetry the scenario never asked for.

        Every request the driver makes while a server starts is a span in that
        server's report, and one abandoned mid-response is a *failed* span.
        So the driver waits for the port, which makes no request, and asks
        ``/health`` once.
        """
        completed = _drive(_scenario(tmp_path))

        seen = json.loads(completed.stderr.strip().splitlines()[-1])
        assert seen.count("GET /health") == 1

    def test_readiness_failure_is_not_retried(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        attempts = 0

        def reset_connection(*_args: object, **kwargs: object) -> None:
            nonlocal attempts
            attempts += 1
            assert kwargs["timeout"] == 17
            raise ConnectionResetError

        monkeypatch.setattr(
            "otel_http_test_client.urllib.request.urlopen", reset_connection
        )

        with pytest.raises(ConnectionResetError):
            wait_for_health("http://127.0.0.1:1", timeout=17)

        assert attempts == 1

    def test_it_reports_what_each_request_came_back_as(
        self, tmp_path: Path
    ) -> None:
        completed = _drive(_scenario(tmp_path))

        assert "GET /status/404 -> 404" in completed.stdout
        assert "POST /items -> 201" in completed.stdout

    def test_the_scenarios_exit_code_is_the_drivers(
        self, tmp_path: Path
    ) -> None:
        # A scenario that fails on the way out — flushing, say — must not be
        # reported as a run that produced everything it meant to.
        completed = _drive(_scenario(tmp_path, exits=3))

        assert completed.returncode == 3

    def test_a_scenario_that_never_answers_is_reported(
        self, tmp_path: Path
    ) -> None:
        completed = _drive(_scenario(tmp_path, "import sys\nsys.exit(2)\n"))

        assert completed.returncode != 0
        assert "exited with 2" in completed.stderr

    def test_a_scenario_answering_off_contract_is_reported(
        self, tmp_path: Path
    ) -> None:
        """The check that keeps eleven languages answering the same traffic.

        A server scenario declares routes in the framework under test,
        so nothing but this stops one of them drifting into answering
        something else and quietly producing an incomparable coverage file.
        """
        drifted = _scenario(tmp_path, mangle='(lambda text: "{}")')

        completed = _drive(drifted)

        assert completed.returncode != 0
        assert "ContractError" in completed.stderr


class TestStoppingWhatAScenarioStarted:
    """A scenario command is often a launcher, so killing it is not enough.

    Every Java scenario runs as ``otel-conformance-java run ...``, which
    starts the JVM and waits for it. A JVM left behind holds the port the next
    run wants and the pipe the runner is reading the scenario's output from,
    which turns one scenario's failure into the runner's own much later
    timeout, reported against the wrong thing.
    """

    def test_one_that_never_starts_takes_its_children_with_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(driver, "_STARTUP_TIMEOUT_SECONDS", 5)

        with pytest.raises(RuntimeError, match="did not listen"):
            driver._serve_and_drive(_launched(tmp_path, _DEAF_STARTER))

        assert _stopped_answering(tmp_path / "port")

    def test_one_that_never_stops_takes_its_children_with_it(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(driver, "_SHUTDOWN_TIMEOUT_SECONDS", 5)

        with pytest.raises(RuntimeError, match="did not exit within"):
            driver._serve_and_drive(_launched(tmp_path, _DEAF_SERVER))

        assert _stopped_answering(tmp_path / "port")


class _UnreapableProcess:
    """A process that will not go away, so cleanup can be tested without one.

    Stands in for the thing the real fallbacks exist for, which cannot be
    produced on demand and does not exist at all on the platform CI runs on.
    """

    def __init__(self, *, dies_when_killed: bool = True) -> None:
        self.pid = 4321
        self.kills = 0
        self.waits: list[float | None] = []
        self._alive = True
        self._dies_when_killed = dies_when_killed

    def poll(self) -> int | None:
        return None if self._alive else 0

    def kill(self) -> None:
        self.kills += 1
        if self._dies_when_killed:
            self._alive = False

    def wait(self, timeout: float | None = None) -> int:
        self.waits.append(timeout)
        if self._alive:
            raise subprocess.TimeoutExpired("scenario", timeout or 0)
        return 0


class TestKillingWhatWillNotStop:
    """Cleanup has to end, because the caller has the real failure to report.

    The driver knows exactly why a scenario failed; the runner only knows that
    the whole command overran, minutes later. Anything here that waits without
    a limit throws away the better message for the worse one.
    """

    def _refuse(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Make the group kill fail the way each platform's can."""

        def refuse(*_args: object, **_kwargs: object) -> None:
            raise subprocess.CalledProcessError(1, "taskkill")

        monkeypatch.setattr(driver, "_kill_windows_tree", refuse)
        monkeypatch.setattr(driver.os, "killpg", refuse, raising=False)

    def _succeed(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Make it report success without anything actually dying."""
        monkeypatch.setattr(driver, "_kill_windows_tree", lambda *_args: None)
        monkeypatch.setattr(
            driver.os, "killpg", lambda *_args: None, raising=False
        )

    def test_a_kill_that_refuses_falls_back_to_the_child(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """`taskkill` reporting that it could not kill must not read as done."""
        self._refuse(monkeypatch)
        process = _UnreapableProcess()

        driver._kill_tree(process)

        assert process.kills == 1

    def test_one_that_survives_everything_is_given_up_on(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        self._succeed(monkeypatch)
        process = _UnreapableProcess(dies_when_killed=False)

        driver._kill_tree(process)

        assert process.kills == 1
        assert process.waits and all(
            timeout is not None for timeout in process.waits
        )


class TestTheCommandLine:
    def test_it_wants_a_url_or_a_command(self) -> None:
        with pytest.raises(SystemExit):
            main([])

    def test_it_will_not_take_both(self) -> None:
        with pytest.raises(SystemExit):
            main(["http://127.0.0.1:1", "--serve", "true"])


def test_the_port_variable_is_documented() -> None:
    """Every language's server scenarios read it, so it is part of the API."""
    readme = Path(__file__).resolve().parents[2] / "README.md"

    assert re.search(
        rf"\b{PORT_VARIABLE}\b", readme.read_text(encoding="utf-8")
    )
