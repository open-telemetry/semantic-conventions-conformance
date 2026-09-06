# Copyright The OpenTelemetry Authors
# SPDX-License-Identifier: Apache-2.0

"""Conformance scenario: an ADK agent run that calls a tool.

The tool actually runs, which is the point: an agent framework executes the
call itself rather than handing it back, so the tool execution is a span of
its own and not just a message in the next request.
"""

import asyncio

from google.adk.agents import LlmAgent
from google.adk.runners import InMemoryRunner
from google.genai import types

APP = "conformance"
USER = "conformance_user"


def get_current_weather(location: str) -> str:
    """Get the current weather in a given location.

    Args:
        location: The city and state, e.g. Boston, MA.
    """
    return f"70 degrees and sunny in {location}"


agent = LlmAgent(
    name="weather_assistant",
    model="gemini-2.0-flash",
    instruction="You are a helpful assistant.",
    tools=[get_current_weather],
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
            role="user",
            parts=[types.Part(text="What's the weather in Seattle today?")],
        ),
    ):
        pass


asyncio.run(main())
