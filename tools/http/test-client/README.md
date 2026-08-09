# HTTP conformance test client

The requests every HTTP conformance scenario makes, shared so the coverage a
client and a server produce is comparable — the same requests against the same
routes.

A **server** scenario is its routes plus one call:

```python
from otel_http_test_client import serve_and_drive

def create_app():
    ...

serve_and_drive(create_app)
```

A **client** scenario hands over its own library, and the runner starts
[`http-mock-server`](../mock-server) for it to call:

```python
import os

from otel_http_test_client import drive

def send(method, url, body):
    ...  # the library under test

drive(os.environ["MOCK_SERVER_URL"], send=send)
```

Each language gets its own implementation under this directory. [`python/`](python)
provides a WSGI server driver and [`java/`](java) provides the language-neutral
request contract for JVM scenarios.

The route contract and the request list are in
[`__init__.py`](python/src/otel_http_test_client/__init__.py) and
[`HttpTestClient.java`](java/src/main/java/io/opentelemetry/conformance/http/HttpTestClient.java).
Both cover health, the templated user route with and without a query string,
the item POST, and 404 and 500 responses.

The Java helper exposes a `Sender` callback for client scenarios. Server
scenarios use its raw HTTP/1.1 socket sender so an attached Java agent cannot
instrument the driver and contaminate server-only coverage.
