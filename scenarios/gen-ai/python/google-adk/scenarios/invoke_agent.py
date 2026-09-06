# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: a single ADK agent run.

Shared by every implementation under ``google-adk/``, which is what makes
their results comparable. Nothing here turns instrumentation on, and nothing
here may: naming one would defeat the sharing. ADK's own spans go to whatever
tracer provider the process has installed, and read the environment for the
rest.

No tools, so the run is the agent and the model call it makes and nothing
else. That is what makes the agent span readable on its own.
"""

import asyncio

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

APP = "conformance"
USER = "conformance_user"

agent = LlmAgent(
    name="weather_assistant",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant.",
    generate_content_config=types.GenerateContentConfig(
        max_output_tokens=100, temperature=0.5
    ),
)


async def main() -> None:
    runner = InMemoryRunner(agent=agent, app_name=APP)
    session = await runner.session_service.create_session(
        app_name=APP, user_id=USER
    )
    async for _ in runner.run_async(
        user_id=USER,
        session_id=session.id,
        new_message=types.Content(
            role="user", parts=[types.Part(text="Say this is a test")]
        ),
    ):
        pass


asyncio.run(main())
