# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: one dspy retriever query.

``dspy.Retrieve`` asks the configured retrieval model for the top ``k``
passages. The retrieval model here ranks a small fixed in-memory document set
by word overlap, so the run makes no LLM call and needs no network, and the
retrieval span is all there is.
"""

import dspy
from dspy.dsp.utils import dotdict

DOCUMENTS = [
    "Seattle is often rainy in the fall and winter.",
    "Phoenix is hot and dry for most of the year.",
    "Chicago gets cold, windy winters.",
    "Miami is warm and humid all year round.",
]


class InMemoryRM:
    collection_name = "weather_facts"

    def __call__(self, query, k):
        words = set(query.lower().split())
        ranked = sorted(
            DOCUMENTS,
            key=lambda doc: (-len(words & set(doc.lower().split())), doc),
        )
        return [dotdict(long_text=doc) for doc in ranked[:k]]


dspy.configure(rm=InMemoryRM())

dspy.Retrieve(k=2)("What is the weather like in Seattle in winter?")
