# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a plain Mistral chat completion.

Shared by every implementation under ``mistral/``, which is what makes their
results comparable. Nothing here turns instrumentation on, and nothing here
may: naming one would defeat the sharing.

``server_url`` is read from the environment because the Mistral SDK has no
base-URL variable of its own — it takes the endpoint as a constructor
argument, so the program has to pass one. Unset, it stays ``None`` and the
client goes to the real API, which is what every other directory gets from the
client library reading its own variable.

The request carries every sampling option the conventions have an attribute
for and the API accepts. Mistral has no top-k.
"""

import os

from mistralai.client import Mistral

Mistral(server_url=os.environ.get("MISTRAL_SERVER_URL")).chat.complete(
    model="mistral-small-latest",
    messages=[
        {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Say this is a test"},
    ],
    max_tokens=100,
    temperature=0.5,
    top_p=0.9,
    frequency_penalty=0.1,
    presence_penalty=0.2,
    stop=["\n\n"],
    random_seed=42,
)
