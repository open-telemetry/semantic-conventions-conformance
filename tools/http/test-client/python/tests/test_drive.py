# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""The driver: what it sends, and how it starts and stops a scenario."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from otel_http_test_client import (
    CONTRACT,
    EXCHANGES,
    PORT_VARIABLE,
    REQUESTS,
    ContractError,
    Exchange,
    respond,
    verify,
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
            exchange
            for exchange in REQUESTS
            if exchange.path == "/status/404"
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
