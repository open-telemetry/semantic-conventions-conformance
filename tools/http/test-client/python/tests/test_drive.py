# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The driver: what it sends, and how it starts and stops a scenario."""

from __future__ import annotations

import asyncio
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

import otel_http_test_client.__main__ as driver
from otel_http_test_client import (
    ACTION_VARIABLE,
    ACTIONS_VARIABLE,
    PORT_VARIABLE,
    ContractError,
    Exchange,
    _carries_the_contracts_body,
    client_headers,
    drive,
    drive_async,
    drive_selected,
    drive_selected_async,
    mock_server_url,
    respond,
    scenario_request,
    verify,
    wait_for_health,
    wait_for_port,
)
from otel_http_test_client.__main__ import main

EXCHANGES = driver._DRIVER_EXCHANGES
REQUESTS = EXCHANGES[1:]


@pytest.fixture(autouse=True)
def runner_action_table(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ACTIONS_VARIABLE, driver._canonical_action_table())


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

# The same scenario, reporting what its environ held rather than what it was
# asked for.
_ENVIRON_SCENARIO = """
import json
import sys

from otel_http_test_client import CONTENT_TYPE, respond, serve

SEEN = []


def app(environ, start_response):
    SEEN.append(
        {key: environ.get(key) for key in ("RAW_URI", "REMOTE_PORT")}
    )

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


serve(lambda: app)
print(json.dumps(SEEN), file=sys.stderr)
"""

# A measured server that records the persistent driver's requests after EOF.
_PERSISTENT_SCENARIO = """
import json
import os
import sys
import threading
from pathlib import Path

from otel_http_test_client import CONTENT_TYPE, respond, serve

SEEN = []


def app(environ, start_response):
    method = environ["REQUEST_METHOD"]
    path = environ.get("RAW_URI", environ["PATH_INFO"])
    length = int(environ.get("CONTENT_LENGTH") or 0)
    request_body = environ["wsgi.input"].read(length).decode() or None
    SEEN.append(
        {
            "method": method,
            "path": path,
            "traceparent": environ.get("HTTP_TRACEPARENT"),
        }
    )
    status, text = respond(method, path, request_body)
    if os.environ.get("BAD_RESPONSE") == path:
        text = '{"wrong": true}'
    body = text.encode()
    start_response(
        f"{status} Status",
        [
            ("Content-Type", CONTENT_TYPE),
            ("Content-Length", str(len(body))),
        ],
    )
    if path == "/health" and os.environ.get("EXIT_AFTER_HEALTH"):
        threading.Timer(0.2, lambda: os._exit(7)).start()
    return [body]


print("inherited child diagnostic", file=sys.stderr, flush=True)
serve(lambda: app)
Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "requests": SEEN,
            "actions": json.loads(
                os.environ["OTEL_CONFORMANCE_SCENARIO_ACTIONS"]
            ),
            "port": os.environ["OTEL_HTTP_SCENARIO_PORT"],
        }
    ),
    encoding="utf-8",
)
sys.exit(int(os.environ.get("CHILD_EXIT_CODE", "0")))
"""

# A scenario command that is a launcher rather than the server itself: it
# starts the real server process, directly or indirectly, and waits for it, so
# the process the driver started is not the process that has to stop.
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
# which is what a server stuck on the way up looks like from the outside. It
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


def _start_persistent_driver(
    tmp_path: Path, **environment: str
) -> tuple[subprocess.Popen[str], Path]:
    scenario = tmp_path / "persistent_scenario.py"
    scenario.write_text(_PERSISTENT_SCENARIO, encoding="utf-8")
    result = tmp_path / "persistent-result.json"
    env = {**os.environ, **environment}
    process = subprocess.Popen(  # noqa: S603
        [
            sys.executable,
            "-m",
            "otel_http_test_client",
            "--persistent",
            "--serve",
            sys.executable,
            str(scenario),
            str(result),
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        env=env,
    )
    return process, result


def _envelope(record: dict[str, object]) -> dict[str, object]:
    stamps = {"started_unix_nano", "completed_unix_nano"}
    return {
        key: value for key, value in record.items() if key not in stamps
    }


def _read_protocol(process: subprocess.Popen[str]) -> dict[str, object]:
    assert process.stdout is not None
    line = process.stdout.readline()
    assert line, (
        f"driver exited before a protocol record with {process.poll()}: "
        f"{process.stderr.read() if process.stderr is not None else ''}"
    )
    record = json.loads(line)
    assert isinstance(record, dict)
    return record


def _send_protocol(
    process: subprocess.Popen[str], record: object
) -> dict[str, object]:
    assert process.stdin is not None
    line = record if isinstance(record, str) else json.dumps(record)
    process.stdin.write(f"{line}\n")
    process.stdin.flush()
    return _read_protocol(process)


def _action_record(
    exchange: Exchange, sequence: int, trace_id: str
) -> dict[str, object]:
    request_document: dict[str, object] = {
        "method": exchange.method,
        "path": exchange.path,
    }
    if exchange.body is not None:
        request_document["body"] = exchange.body
    return {
        "version": "jsonl-v1",
        "type": "action",
        "sequence": sequence,
        "scenario": f"{sequence - 1:04d}",
        "correlation_trace_id": trace_id,
        "action": {
            "request": request_document,
            "response": {
                "status": exchange.status,
                "body": exchange.response_body,
            },
        },
    }


def _action_json(exchange: Exchange) -> str:
    return json.dumps(_action_record(exchange, 1, "11" * 16)["action"])


def _finish_persistent_driver(
    process: subprocess.Popen[str],
) -> tuple[dict[str, object], str]:
    assert process.stdin is not None
    assert process.stderr is not None
    process.stdin.close()
    stopped = _read_protocol(process)
    stderr = process.stderr.read()
    process.wait(timeout=30)
    return stopped, stderr


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
    def test_the_complete_runner_table_includes_readiness(self) -> None:
        assert len(REQUESTS) == len(EXCHANGES) - 1
        assert EXCHANGES[0].readiness
        assert all(not exchange.readiness for exchange in REQUESTS)

    def test_every_request_has_a_description(self) -> None:
        assert all(exchange.description for exchange in EXCHANGES)

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

    def test_the_driver_keeps_sending_every_request(self) -> None:
        seen: list[str] = []

        def send(method: str, url: str, body: str | None) -> tuple[int, str]:
            seen.append(f"{method} {url}")
            return respond(method, url.removeprefix("http://server"), body)

        drive("http://server", send)

        assert seen == [
            f"{exchange.method} http://server{exchange.path}"
            for exchange in REQUESTS
        ]

    def test_the_async_driver_keeps_sending_every_request(self) -> None:
        seen: list[str] = []

        async def send(
            method: str, url: str, body: str | None
        ) -> tuple[int, str]:
            seen.append(f"{method} {url}")
            return respond(method, url.removeprefix("http://server"), body)

        asyncio.run(drive_async("http://server", send))

        assert seen == [
            f"{exchange.method} http://server{exchange.path}"
            for exchange in REQUESTS
        ]

    def test_the_selected_driver_sends_one_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []

        def send(method: str, url: str, body: str | None) -> tuple[int, str]:
            seen.append(f"{method} {url}")
            return respond(method, url.removeprefix("http://server"), body)

        for request_exchange in REQUESTS:
            monkeypatch.setenv(ACTION_VARIABLE, _action_json(request_exchange))
            drive_selected("http://server", send)

        assert seen == [
            f"{exchange.method} http://server{exchange.path}"
            for exchange in REQUESTS
        ]

    def test_the_selected_async_driver_sends_one_request(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        seen: list[str] = []

        async def send(
            method: str, url: str, body: str | None
        ) -> tuple[int, str]:
            seen.append(f"{method} {url}")
            return respond(method, url.removeprefix("http://server"), body)

        for request_exchange in REQUESTS:
            monkeypatch.setenv(ACTION_VARIABLE, _action_json(request_exchange))
            asyncio.run(drive_selected_async("http://server", send))

        assert seen == [
            f"{exchange.method} http://server{exchange.path}"
            for exchange in REQUESTS
        ]

    def test_each_singular_action_selects_one_independent_request(
        self,
    ) -> None:
        selected = [
            scenario_request(_action_json(request)) for request in REQUESTS
        ]
        assert [
            (request.method, request.path, request.body, request.status)
            for request in selected
        ] == [
            (request.method, request.path, request.body, request.status)
            for request in REQUESTS
        ]

    def test_missing_and_malformed_action_variables_say_which_one(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ACTION_VARIABLE, raising=False)
        with pytest.raises(
            RuntimeError, match=f"{ACTION_VARIABLE} is not set"
        ):
            scenario_request()
        monkeypatch.setenv(ACTION_VARIABLE, "{")
        with pytest.raises(RuntimeError, match="malformed JSON"):
            scenario_request()

    def test_unknown_action_fields_are_rejected(self) -> None:
        action = json.loads(_action_json(REQUESTS[0]))
        action["extra"] = True
        with pytest.raises(RuntimeError, match="unknown field"):
            scenario_request(json.dumps(action))

    def test_missing_action_table_says_which_variable(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv(ACTIONS_VARIABLE)
        with pytest.raises(
            RuntimeError, match=f"{ACTIONS_VARIABLE} is not set"
        ):
            respond("GET", "/health")
        monkeypatch.setenv(ACTIONS_VARIABLE, "{")
        with pytest.raises(RuntimeError, match="malformed JSON"):
            respond("GET", "/health")


class TestClientWorkloads:
    def test_mock_server_url_comes_from_the_runner(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("MOCK_SERVER_URL", "http://mock-server")

        assert mock_server_url() == "http://mock-server"

    def test_missing_mock_server_url_explains_who_sets_it(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("MOCK_SERVER_URL", raising=False)

        with pytest.raises(RuntimeError, match="the runner publishes it"):
            mock_server_url()

    def test_every_request_has_the_fixed_user_agent(self) -> None:
        assert client_headers(None) == {
            "User-Agent": "otel-http-conformance/1"
        }

    def test_a_request_body_adds_its_content_type(self) -> None:
        assert client_headers("{}") == {
            "User-Agent": "otel-http-conformance/1",
            "Content-Type": "application/json",
        }

    def test_a_response_outside_the_contract_does_not_fail_the_scenario(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ACTION_VARIABLE, _action_json(REQUESTS[0]))

        drive_selected("http://server", lambda *_args: (599, "not json"))

    def test_the_async_client_does_not_validate_the_response(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ACTION_VARIABLE, _action_json(REQUESTS[0]))

        async def send(*_args: object) -> tuple[int, str]:
            return 599, "not json"

        asyncio.run(drive_selected_async("http://server", send))

    def test_json_numbers_do_not_stand_in_for_booleans(self) -> None:
        exchange = scenario_request(_action_json(REQUESTS[2]))

        with pytest.raises(ContractError, match="contract's request answers"):
            verify(
                exchange,
                exchange.status,
                '{"created": 1, "payload": {"name": "widget"}}',
            )


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


class TestCheckingTheRequestBody:
    """What the mock server asks for, and a server scenario does not.

    ``otel-http-drive`` compares the echoed body, so a server scenario that
    never read the request already fails. Nothing reads the answer a client
    scenario receives, so the mock server is the only place a client that
    never sent the body can be caught.
    """

    def test_a_body_the_contract_declares_must_arrive(self) -> None:
        assert respond("POST", "/items", check_request_body=True)[0] == 400

    def test_a_different_body_is_refused(self) -> None:
        answer = respond(
            "POST", "/items", '{"name": "gadget"}', check_request_body=True
        )

        assert answer[0] == 400

    def test_a_body_that_is_not_json_is_refused(self) -> None:
        answer = respond("POST", "/items", "<html>", check_request_body=True)

        assert answer[0] == 400

    def test_formatting_is_not_part_of_the_contract(self) -> None:
        """Spacing and key order are the client library's JSON writer's call."""
        status, body = respond(
            "POST", "/items", '{"name":"widget"}', check_request_body=True
        )

        assert status == 201
        assert json.loads(body)["payload"] == {"name": "widget"}

    def test_a_number_does_not_stand_in_for_a_boolean(self) -> None:
        """Python reads ``1`` and ``true`` as equal, and the contract does not.

        No request the contract declares carries a boolean today, so this
        asks the check itself rather than going through the mock server.
        """
        exchange = Exchange(
            method="POST",
            path="/items",
            body='{"created": true}',
            status=201,
            response_body="{}",
            readiness=False,
            description="a request whose body carries a JSON boolean",
        )

        assert _carries_the_contracts_body(exchange, '{"created": true}')
        assert not _carries_the_contracts_body(exchange, '{"created": 1}')

    def test_a_request_the_contract_sends_no_body_for_is_answered(
        self,
    ) -> None:
        assert respond("GET", "/users/123", check_request_body=True)[0] == 200


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


class TestPersistentServerDriving:
    def test_protocol_frames_each_request_and_keeps_readiness_isolated(
        self, tmp_path: Path
    ) -> None:
        started = time.time_ns()
        process, result_path = _start_persistent_driver(tmp_path)

        ready = _read_protocol(process)
        assert _envelope(ready) == {
            "sequence": 0,
            "type": "ready",
            "version": "jsonl-v1",
        }
        trace_ids = tuple(f"{sequence + 16:032x}" for sequence in range(1, 6))
        responses = [
            _send_protocol(
                process,
                _action_record(exchange, sequence, trace_ids[sequence - 1]),
            )
            for sequence, exchange in enumerate(REQUESTS, start=1)
        ]
        stopped, stderr = _finish_persistent_driver(process)

        assert [_envelope(response) for response in responses] == [
            {
                "sequence": sequence,
                "type": "action_complete",
                "version": "jsonl-v1",
            }
            for sequence in range(1, 6)
        ]
        # Each exchange is stamped where the driver sent it and where it saw
        # the answer, so the runner never judges an aggregation interval by
        # when it read the record. They only ever move forward.
        stamps = [
            stamp
            for record in (ready, *responses)
            for stamp in (
                record["started_unix_nano"],
                record["completed_unix_nano"],
            )
        ]
        assert all(isinstance(stamp, int) for stamp in stamps)
        assert stamps == sorted(stamps)
        assert started < stamps[0] and stamps[-1] <= time.time_ns()
        assert stopped == {
            "sequence": 6,
            "type": "stopped",
            "version": "jsonl-v1",
        }
        assert process.returncode == 0
        recorded = json.loads(result_path.read_text(encoding="utf-8"))
        requests = recorded["requests"]
        assert [item["path"] for item in requests] == [
            "/health",
            *[exchange.path for exchange in REQUESTS],
        ]
        assert len(requests) == 1 + len(REQUESTS)
        traceparents = [item["traceparent"] for item in requests]
        assert all(
            re.fullmatch(r"00-[0-9a-f]{32}-[0-9a-f]{16}-01", value)
            for value in traceparents
        )
        assert traceparents[0].split("-")[1] == driver._BOOTSTRAP_TRACE_ID
        assert [value.split("-")[1] for value in traceparents[1:]] == list(
            trace_ids
        )
        assert traceparents[0].split("-")[1] not in trace_ids
        assert recorded["actions"] == json.loads(
            driver._canonical_action_table()
        )
        assert len(recorded["actions"]) == len(EXCHANGES)
        assert recorded["actions"][0]["request"]["path"] == "/health"
        assert recorded["port"].isdigit()
        assert "inherited child diagnostic" in stderr
        assert process.stdout is not None
        assert process.stdout.read() == ""

    def test_response_drift_emits_action_error_before_shutdown(
        self, tmp_path: Path
    ) -> None:
        exchange = REQUESTS[0]
        process, result_path = _start_persistent_driver(
            tmp_path, BAD_RESPONSE=exchange.path
        )
        assert _read_protocol(process)["type"] == "ready"

        response = _send_protocol(
            process, _action_record(exchange, 1, "33" * 16)
        )
        stopped, _stderr = _finish_persistent_driver(process)

        assert response["type"] == "action_error"
        assert response["sequence"] == 1
        assert "ContractError" in str(response["error"])
        assert "answers" in str(response["error"])
        assert stopped["type"] == "stopped"
        assert stopped["sequence"] == 2
        recorded = json.loads(result_path.read_text(encoding="utf-8"))
        assert [item["path"] for item in recorded["requests"]] == [
            "/health",
            exchange.path,
        ]

    @pytest.mark.parametrize(
        "invalid, expected",
        [
            ("not json", "malformed jsonl-v1 action"),
            (
                _action_record(REQUESTS[0], 2, "44" * 16),
                "expected action sequence 1",
            ),
        ],
    )
    def test_invalid_input_fails_closed_without_an_external_action(
        self, tmp_path: Path, invalid: object, expected: str
    ) -> None:
        process, result_path = _start_persistent_driver(tmp_path)
        assert _read_protocol(process)["type"] == "ready"

        response = _send_protocol(process, invalid)
        assert response["type"] == "action_error"
        assert response["sequence"] == 1
        assert expected in str(response["error"])

        assert process.stdin is not None
        process.stdin.write(
            json.dumps(_action_record(REQUESTS[0], 1, "55" * 16)) + "\n"
        )
        process.stdin.flush()
        stopped, _stderr = _finish_persistent_driver(process)

        assert stopped["type"] == "stopped"
        recorded = json.loads(result_path.read_text(encoding="utf-8"))
        assert [item["path"] for item in recorded["requests"]] == ["/health"]

    def test_eof_waits_for_child_and_returns_its_result(
        self, tmp_path: Path
    ) -> None:
        process, result_path = _start_persistent_driver(
            tmp_path, CHILD_EXIT_CODE="3"
        )
        assert _read_protocol(process)["type"] == "ready"

        stopped, _stderr = _finish_persistent_driver(process)

        assert stopped == {
            "sequence": 1,
            "type": "stopped",
            "version": "jsonl-v1",
        }
        assert process.returncode == 3
        assert result_path.exists()

    def test_early_child_exit_is_an_action_error(self, tmp_path: Path) -> None:
        process, _result_path = _start_persistent_driver(
            tmp_path, EXIT_AFTER_HEALTH="1"
        )
        assert _read_protocol(process)["type"] == "ready"
        time.sleep(0.5)

        response = _send_protocol(
            process, _action_record(REQUESTS[0], 1, "66" * 16)
        )
        stopped, _stderr = _finish_persistent_driver(process)

        assert response["type"] == "action_error"
        assert "exited with 7 before the request" in str(response["error"])
        assert stopped["type"] == "stopped"
        assert process.returncode == 7

    def test_readiness_response_is_validated_before_ready(
        self, tmp_path: Path
    ) -> None:
        process, _result_path = _start_persistent_driver(
            tmp_path, BAD_RESPONSE="/health"
        )
        assert process.stdout is not None
        assert process.stderr is not None

        stdout, stderr = process.communicate(timeout=30)

        assert process.returncode != 0
        assert stdout == ""
        assert "ContractError" in stderr


class TestStoppingWhatAScenarioStarted:
    """A scenario command is often a launcher, so killing it is not enough.

    A launcher starts the real server as a descendant and waits for it. A
    server left behind holds the port the next run wants and the pipe the
    runner is reading the scenario's output from, which turns one scenario's
    failure into the runner's own much later timeout, reported against the
    wrong thing.
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

    def test_external_abort_takes_the_measured_process_tree_with_it(
        self, tmp_path: Path
    ) -> None:
        command = _launched(tmp_path, _DEAF_SERVER)
        process = subprocess.Popen(  # noqa: S603
            [
                sys.executable,
                "-m",
                "otel_http_test_client",
                "--persistent",
                "--serve",
                *command,
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
        )
        assert _read_protocol(process)["type"] == "ready"

        process.terminate()
        process.wait(timeout=30)
        if process.stderr is not None:
            process.stderr.read()

        assert _stopped_answering(tmp_path / "port")


class TestWhatAServerScenarioIsGiven:
    """``serve()`` is the harness, so what it puts in the environ decides what
    an instrumentation *can* record."""

    def test_it_supplies_what_a_real_wsgi_server_does(
        self, tmp_path: Path
    ) -> None:
        """A WSGI instrumentation reads ``url.path`` and ``url.query`` from
        ``RAW_URI`` and ``client.port`` from ``REMOTE_PORT``. PEP 3333 defines
        neither, so a bare reference server would be the reason they are
        missing from a coverage file.
        """
        completed = _drive(_scenario(tmp_path, _ENVIRON_SCENARIO))

        assert completed.returncode == 0, completed.stderr
        seen = json.loads(completed.stderr.strip().splitlines()[-1])
        assert "/users/123?fields=name&verbose=true" in [
            request["RAW_URI"] for request in seen
        ]
        assert all(request["REMOTE_PORT"] for request in seen)


class TestTheCommandLine:
    def test_it_wants_a_url_or_a_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            main([])
        assert (
            "give either a base URL or --serve COMMAND"
            in capsys.readouterr().err
        )

    def test_it_will_not_take_both(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            main(["http://127.0.0.1:1", "--serve", "true"])
        assert "not both" in capsys.readouterr().err

    def test_serve_requires_a_command(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        with pytest.raises(SystemExit):
            main(["--serve"])
        assert "--serve requires COMMAND" in capsys.readouterr().err


def test_the_port_variable_is_documented() -> None:
    """Every language's server scenarios read it, so it is part of the API."""
    readme = Path(__file__).resolve().parents[2] / "README.md"

    assert re.search(
        rf"\b{PORT_VARIABLE}\b", readme.read_text(encoding="utf-8")
    )


class TestTheRunnerOwnedActionTable:
    """The runner parses the contract; the driver only hands the table on."""

    def test_it_reaches_the_scenario_exactly_as_it_arrived(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        table = json.dumps(
            [
                {
                    "request": {"method": "GET", "path": "/custom/ready"},
                    "response": {"status": 200, "body": '{"ready": true}'},
                },
                {
                    "request": {"method": "GET", "path": "/custom/first"},
                    "response": {"status": 201, "body": '{"created": 1}'},
                },
            ]
        )
        monkeypatch.setenv(ACTIONS_VARIABLE, table)
        process, result = _start_persistent_driver(tmp_path)

        ready = _read_protocol(process)
        assert _envelope(ready) == {
            "version": "jsonl-v1",
            "type": "ready",
            "sequence": 0,
        }
        exchange = Exchange(
            "GET", "/custom/first", None, 201, '{"created": 1}', False, ""
        )
        complete = _send_protocol(
            process, _action_record(exchange, 1, "22" * 16)
        )
        assert complete["type"] == "action_complete", complete
        _finish_persistent_driver(process)

        received = json.loads(result.read_text(encoding="utf-8"))
        assert json.dumps(received["actions"]) == table
        assert [
            request["path"] for request in received["requests"]
        ] == ["/custom/ready", "/custom/first"]

    def test_a_malformed_table_fails_before_the_scenario_starts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv(ACTIONS_VARIABLE, "[]")
        process, result = _start_persistent_driver(tmp_path)

        assert process.stdout is not None
        assert process.stderr is not None
        assert process.stdout.read() == ""
        assert "non-empty JSON array of actions" in process.stderr.read()
        assert process.wait(timeout=30) != 0
        assert not result.exists()

    def test_a_served_run_drives_it_rather_than_the_packaged_contract(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``--serve`` without ``--persistent`` is driven by the same table.

        The scenario answers whatever table it was given, so driving the
        packaged contract instead would send requests the server has no route
        for — and would measure a package against exchanges it never declared.
        """
        monkeypatch.setenv(
            ACTIONS_VARIABLE,
            json.dumps(
                [
                    {
                        "request": {"method": "GET", "path": "/custom/ready"},
                        "response": {
                            "status": 200,
                            "body": '{"ready": true}',
                        },
                    },
                    {
                        "request": {"method": "GET", "path": "/custom/first"},
                        "response": {
                            "status": 201,
                            "body": '{"created": 1}',
                        },
                    },
                ]
            ),
        )

        completed = _drive(_scenario(tmp_path))

        assert completed.returncode == 0, completed.stderr
        seen = json.loads(completed.stderr.strip().splitlines()[-1])
        assert seen == ["GET /custom/ready", "GET /custom/first"]
        assert "GET /custom/first -> 201" in completed.stdout
