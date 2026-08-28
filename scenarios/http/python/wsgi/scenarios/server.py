# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""A bare WSGI workload, with no instrumentation attached."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from http import HTTPStatus
from typing import BinaryIO, cast

from otel_http_test_client import CONTENT_TYPE, respond


def application(
    environ: dict[str, object],
    start_response: Callable[[str, list[tuple[str, str]]], object],
) -> Iterable[bytes]:
    method = str(environ["REQUEST_METHOD"])
    path = str(environ["PATH_INFO"])
    length = int(environ.get("CONTENT_LENGTH") or 0)
    stream = cast(BinaryIO, environ["wsgi.input"])
    body = stream.read(length).decode() if length else None
    status, payload = respond(method, path, body)
    payload_bytes = payload.encode()
    start_response(
        f"{status} {HTTPStatus(status).phrase}",
        [
            ("Content-Type", CONTENT_TYPE),
            ("Content-Length", str(len(payload_bytes))),
        ],
    )
    return [payload_bytes]
