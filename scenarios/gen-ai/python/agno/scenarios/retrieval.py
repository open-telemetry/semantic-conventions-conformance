# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: one agno knowledge search, with no model call.

Knowledge needs a vector database. Qdrant's local mode keeps it in memory in
this process, so inserting the documents and running the query only reach
the mock for embeddings.
"""

from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.knowledge.knowledge import Knowledge
from agno.vectordb.qdrant import Qdrant

knowledge = Knowledge(
    name="weather_notes",
    vector_db=Qdrant(
        collection="weather_notes",
        location=":memory:",
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
)
knowledge.insert(name="seattle", text_content="Seattle is rainy in the winter.")
knowledge.insert(name="phoenix", text_content="Phoenix is hot and dry in the summer.")
knowledge.insert(name="denver", text_content="Denver gets snow in the mountains.")

knowledge.search("What is the weather in Seattle?", max_results=2)
