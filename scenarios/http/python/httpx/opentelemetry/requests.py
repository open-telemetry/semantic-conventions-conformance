# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an httpx client making the standard requests.

The mirror of the server scenarios — the same requests, sent by the library
under test instead of at it. The runner starts the server they go to and
passes its URL in as ``MOCK_SERVER_URL``.
"""

import os

from otel_http_test_client import drive


def send(method, url, body):
    import httpx

    headers = {"Content-Type": "application/json"} if body is not None else {}
    response = httpx.request(method, url, content=body, headers=headers)
    return response.status_code, response.text


drive(os.environ["MOCK_SERVER_URL"], send=send)
