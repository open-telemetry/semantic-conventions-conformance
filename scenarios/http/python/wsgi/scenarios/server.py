# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A bare WSGI workload, with no instrumentation attached."""

from __future__ import annotations

from collections.abc import Callable, Iterable

from otel_http_test_client import CONTENT_TYPE, respond


def application(
    environ: dict[str, object],
    start_response: Callable[[str, list[tuple[str, str]]], object],
) -> Iterable[bytes]:
    method = str(environ["REQUEST_METHOD"])
    path = str(environ["PATH_INFO"])
    length = int(environ.get("CONTENT_LENGTH") or 0)
    stream = environ["wsgi.input"]
    body = stream.read(length).decode() if length else None
    status, payload = respond(method, path, body)
    start_response(
        f"{status} {_status_text(status)}",
        [
            ("Content-Type", CONTENT_TYPE),
            ("Content-Length", str(len(payload.encode()))),
        ],
    )
    return [payload.encode()]


def _status_text(status: int) -> str:
    return {
        200: "OK",
        201: "Created",
        404: "Not Found",
        500: "Internal Server Error",
    }[status]
