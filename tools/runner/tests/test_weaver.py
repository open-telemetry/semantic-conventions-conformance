# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Weaver HTTP readiness and shutdown protocols."""

import os
import subprocess
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, Mock

import pytest
from urllib3 import HTTPResponse
from urllib3.exceptions import (
    ConnectTimeoutError,
    NewConnectionError,
    ProtocolError,
    ReadTimeoutError,
)
from urllib3.util import Timeout as HttpTimeout

pytest.importorskip("opentelemetry.test.weaver_live_check")

from opentelemetry.conformance import _weaver
from opentelemetry.conformance._session import _start_weaver


@pytest.fixture
def starting_weaver() -> _weaver.WeaverLiveCheck:
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = False
    weaver._stopped = False
    weaver._admin_port = 1234
    weaver._process = Mock()
    weaver._process.poll.return_value = None
    weaver._command = ["weaver"]
    weaver._stdout_path = None
    weaver._stderr_path = None
    return weaver


@pytest.fixture
def health(monkeypatch: pytest.MonkeyPatch) -> Mock:
    pool = MagicMock()
    pool.__enter__.return_value = pool
    monkeypatch.setattr(_weaver, "HTTPConnectionPool", Mock(return_value=pool))
    return pool.urlopen


@pytest.fixture
def clock(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    now = [0.0]
    monkeypatch.delenv("OTEL_CONFORMANCE_WEAVER_STARTUP_TIMEOUT", raising=False)
    monkeypatch.setattr(_weaver.time, "monotonic", lambda: now[0])

    def sleep(seconds: float) -> None:
        now[0] += seconds

    monkeypatch.setattr(_weaver.time, "sleep", sleep)
    return now


def test_readiness_waits_for_slow_startup(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    health: Mock,
) -> None:
    response = HTTPResponse(body=BytesIO(), status=200, preload_content=False)

    def get(
        method: str, url: str, *, timeout: HttpTimeout, **kwargs: object
    ) -> HTTPResponse:
        assert method == "GET"
        assert url == "/health"
        assert timeout.total == 1.0
        assert kwargs == {
            "retries": False,
            "redirect": False,
            "preload_content": False,
        }
        if clock[0] < 20:
            clock[0] += 1.0
            raise ConnectTimeoutError("not listening yet")
        return response

    health.side_effect = get

    starting_weaver._wait_for_ready()

    assert clock[0] == pytest.approx(20.9)
    assert health.call_count == 20
    assert response.closed
    starting_weaver._process.terminate.assert_not_called()


def test_readiness_bounds_requests_and_total_wait(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    monkeypatch: pytest.MonkeyPatch,
    health: Mock,
) -> None:
    monkeypatch.setenv("OTEL_CONFORMANCE_WEAVER_STARTUP_TIMEOUT", "2.5")
    timeouts: list[float] = []
    error = ReadTimeoutError(None, "/health", "health request timed out")

    def get(
        method: str, url: str, *, timeout: HttpTimeout, **kwargs: object
    ) -> HTTPResponse:
        assert isinstance(timeout.total, float)
        timeouts.append(timeout.total)
        clock[0] += timeout.total
        raise error

    health.side_effect = get

    with pytest.raises(TimeoutError, match="within 2.5s") as raised:
        starting_weaver._wait_for_ready()

    assert clock[0] == 2.5
    assert timeouts == pytest.approx([1.0, 1.0, 0.3])
    assert raised.value.__cause__ is error
    assert not starting_weaver._ready


def test_readiness_default_timeout_is_120_seconds(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    health: Mock,
) -> None:
    def get(
        method: str, url: str, *, timeout: HttpTimeout, **kwargs: object
    ) -> HTTPResponse:
        assert isinstance(timeout.total, float)
        assert 0 < timeout.total <= 1.0
        assert timeout.total <= 120.0 - clock[0]
        clock[0] += timeout.total
        raise ConnectTimeoutError("not listening")

    health.side_effect = get

    with pytest.raises(TimeoutError, match="within 120.0s"):
        starting_weaver._wait_for_ready()

    assert clock[0] == 120.0
    assert health.call_count == 110


@pytest.mark.parametrize("status", [204, 301, 503])
def test_nonready_health_response_times_out(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    monkeypatch: pytest.MonkeyPatch,
    health: Mock,
    status: int,
) -> None:
    monkeypatch.setenv("OTEL_CONFORMANCE_WEAVER_STARTUP_TIMEOUT", "0.25")
    health.side_effect = lambda *args, **kwargs: HTTPResponse(
        body=BytesIO(), status=status, preload_content=False
    )

    with pytest.raises(TimeoutError, match="within 0.25s"):
        starting_weaver._wait_for_ready()

    assert clock[0] == 0.25
    assert health.call_count == 3
    assert [call.kwargs["timeout"].total for call in health.call_args_list] == (
        pytest.approx([0.25, 0.15, 0.05])
    )
    assert not starting_weaver._ready


@pytest.mark.parametrize(
    "error",
    [
        ConnectTimeoutError("connection refused"),
        NewConnectionError(None, "connection refused"),
        ReadTimeoutError(None, "/health", "slow"),
        ProtocolError("connection closed"),
    ],
)
def test_readiness_recovers_from_connection_errors(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    health: Mock,
    error: Exception,
) -> None:
    health.side_effect = [
        error,
        HTTPResponse(body=BytesIO(), status=200, preload_content=False),
    ]

    starting_weaver._wait_for_ready()

    assert clock[0] == 0.1
    assert health.call_count == 2


@pytest.mark.parametrize("exit_code", [0, 17])
def test_readiness_fails_promptly_when_process_exits(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    health: Mock,
    exit_code: int,
) -> None:
    starting_weaver._process.poll.return_value = exit_code

    with pytest.raises(RuntimeError, match=f"exited unexpectedly \\(code {exit_code}\\)"):
        starting_weaver._wait_for_ready()

    assert clock[0] == 0.0
    health.assert_not_called()


def test_readiness_detects_process_exit_during_health_request(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    health: Mock,
) -> None:
    starting_weaver._process.poll.side_effect = [None, 23]
    health.side_effect = ProtocolError("connection closed")

    with pytest.raises(RuntimeError, match="exited unexpectedly \\(code 23\\)"):
        starting_weaver._wait_for_ready()

    assert clock[0] == 0.0
    assert starting_weaver._process.poll.call_count == 2


def test_health_response_after_deadline_is_not_ready(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    monkeypatch: pytest.MonkeyPatch,
    health: Mock,
) -> None:
    monkeypatch.setenv("OTEL_CONFORMANCE_WEAVER_STARTUP_TIMEOUT", "0.5")
    response = HTTPResponse(body=BytesIO(), status=200, preload_content=False)

    def get(
        method: str, url: str, *, timeout: HttpTimeout, **kwargs: object
    ) -> HTTPResponse:
        assert timeout.total == 0.5
        clock[0] += 0.5
        return response

    health.side_effect = get

    with pytest.raises(TimeoutError, match="within 0.5s"):
        starting_weaver._wait_for_ready()

    assert clock[0] == 0.5
    assert not starting_weaver._ready


def test_startup_failure_logs_and_cleans_up(
    starting_weaver: _weaver.WeaverLiveCheck,
    clock: list[float],
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    health: Mock,
) -> None:
    monkeypatch.setenv("OTEL_CONFORMANCE_WEAVER_STARTUP_TIMEOUT", "0.25")
    process = starting_weaver._process
    paths: list[Path] = []

    def popen(command: list[str], *, stdout: int, stderr: int) -> Mock:
        assert starting_weaver._stdout_path is not None
        assert starting_weaver._stderr_path is not None
        paths.extend(
            [Path(starting_weaver._stdout_path), Path(starting_weaver._stderr_path)]
        )
        os.write(stderr, b"registry still resolving")
        return process

    monkeypatch.setattr(subprocess, "Popen", popen)
    health.side_effect = ConnectTimeoutError("not listening")

    with pytest.raises(TimeoutError, match="within 0.25s"):
        with _start_weaver(lambda: starting_weaver):
            pytest.fail("startup should fail before yielding")

    assert clock[0] == 0.25
    assert "WeaverLiveCheck did not start" in caplog.text
    assert "registry still resolving" in caplog.text
    assert starting_weaver._stdout_path is None
    assert starting_weaver._stderr_path is None
    assert all(not path.exists() for path in paths)
    assert starting_weaver._stopped


def test_end_reads_report_before_shutdown(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    process = Mock()
    process.wait.return_value = 0
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._stopped = False
    weaver._admin_port = 1234
    weaver._process = process

    def post(url: str, *, timeout: int) -> Mock:
        calls.append(url.rsplit("/", 1)[-1])
        assert timeout == 15
        return Mock(json=lambda: {"state": "stopped", "report": True})

    def get(url: str, *, timeout: int) -> Mock:
        calls.append(url.rsplit("/", 1)[-1])
        assert timeout == 15
        return Mock(json=lambda: {"samples": []})

    monkeypatch.setattr(_weaver, "post", post)
    monkeypatch.setattr(_weaver, "get", get)

    report = weaver.end(timeout=15)

    assert report["samples"] == []
    assert calls == ["stop", "report", "shutdown"]
    process.wait.assert_called_once_with(timeout=15)


@pytest.mark.parametrize("samples", [[], [{"span": {"name": "example"}}]])
def test_end_reads_legacy_stop_report(
    samples: list[dict[str, object]], monkeypatch: pytest.MonkeyPatch
) -> None:
    process = Mock()
    process.wait.return_value = 0
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._stopped = False
    weaver._admin_port = 1234
    weaver._process = process
    post = Mock(
        return_value=Mock(json=lambda: {"samples": samples, "statistics": {}})
    )
    get = Mock()
    monkeypatch.setattr(_weaver, "post", post)
    monkeypatch.setattr(_weaver, "get", get)

    report = weaver.end(timeout=15)

    assert report["samples"] == samples
    assert report["statistics"] == {}
    post.assert_called_once_with("http://localhost:1234/stop", timeout=15)
    get.assert_not_called()
    process.wait.assert_called_once_with(timeout=15)


def test_shutdown_follows_report_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[str] = []
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._admin_port = 1234
    weaver._process = Mock()
    monkeypatch.setattr(weaver, "_read_weaver_logs", lambda: "")

    def post(url: str, *, timeout: int) -> Mock:
        calls.append(url.rsplit("/", 1)[-1])
        return Mock(json=lambda: {"state": "stopped", "report": True})

    def get(url: str, *, timeout: int) -> Mock:
        calls.append(url.rsplit("/", 1)[-1])
        response = Mock()
        response.raise_for_status.side_effect = RuntimeError("report failed")
        return response

    monkeypatch.setattr(_weaver, "post", post)
    monkeypatch.setattr(_weaver, "get", get)

    with pytest.raises(RuntimeError, match="report failed"):
        weaver._do_stop(timeout=15)

    assert calls == ["stop", "report", "shutdown"]


def test_shutdown_follows_missing_report(monkeypatch: pytest.MonkeyPatch) -> None:
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._admin_port = 1234
    weaver._process = Mock()
    monkeypatch.setattr(weaver, "_read_weaver_logs", lambda: "")
    post = Mock(
        return_value=Mock(json=lambda: {"state": "stopped", "report": False})
    )
    get = Mock()
    monkeypatch.setattr(_weaver, "post", post)
    monkeypatch.setattr(_weaver, "get", get)

    with pytest.raises(RuntimeError, match="stopped without an HTTP report"):
        weaver._do_stop(timeout=15)

    assert [call.args[0] for call in post.call_args_list] == [
        "http://localhost:1234/stop",
        "http://localhost:1234/shutdown",
    ]
    get.assert_not_called()
    weaver._process.wait.assert_not_called()


@pytest.mark.parametrize("response", [None, [], {}, {"samples": []}])
def test_unexpected_stop_response_is_reported(
    response: object,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    weaver = _weaver.WeaverLiveCheck.__new__(_weaver.WeaverLiveCheck)
    weaver._ready = True
    weaver._admin_port = 1234
    weaver._process = Mock()
    monkeypatch.setattr(weaver, "_read_weaver_logs", lambda: "weaver log")
    monkeypatch.setattr(_weaver, "post", Mock(return_value=Mock(json=lambda: response)))
    get = Mock()
    monkeypatch.setattr(_weaver, "get", get)

    with pytest.raises(RuntimeError, match="Unexpected Weaver /stop response"):
        weaver._do_stop(timeout=15)

    get.assert_not_called()
    weaver._process.wait.assert_not_called()
    assert "Unexpected Weaver /stop response" in caplog.text
    assert "weaver log" in caplog.text
