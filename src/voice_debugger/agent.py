"""A voice-only agent using Google's API directly, without LiveKit Inference."""

import asyncio
import os

from livekit import agents
from livekit.agents import Agent, AgentServer, AgentSession, room_io
from livekit.plugins import google

from .config import AGENT_NAME, SESSION_LIMIT_SECONDS, load_settings

INSTRUCTIONS = """You are Voice Debugger, a patient voice companion helping students
troubleshoot Python setup problems in VS Code. This is a voice-only experiment.
You cannot see the user's screen, inspect files, run commands, or change their computer.
Ask them to describe or read the exact error. Do not imply you performed any action.
Focus on Python interpreters, virtual environments, and missing packages.
Ask one question or suggest one small step at a time, then wait for the answer.
Use short spoken replies, usually one to three sentences. Explain jargon simply.
If interrupted or corrected, follow the latest correction and stop repeating the old step.
Keep track of what has been tried. If a step fails, use the new evidence to choose a next step.
Never ask for passwords, API keys, private files, or other secrets.
Avoid destructive commands, system-wide installs, and changes unrelated to this problem.
Ask before recommending a change to the environment. When unsure, say so and clarify.
Never declare a problem solved until the user reruns the program and reports success.
If stuck, summarize the error and attempted fixes for a human helper.
"""

server = AgentServer()


@server.rtc_session(agent_name=AGENT_NAME)
async def entrypoint(ctx: agents.JobContext):
    settings = load_settings()
    session = AgentSession(
        llm=google.realtime.RealtimeModel(
            model=settings.model,
            api_key=settings.google_api_key,
            vertexai=False,
            voice="Puck",
        ),
    )
    await session.start(
        room=ctx.room,
        agent=Agent(instructions=INSTRUCTIONS),
        room_options=room_io.RoomOptions(
            video_input=False,
            text_input=False,
            close_on_disconnect=True,
            delete_room_on_close=True,
        ),
    )

    async def expire_session():
        await asyncio.sleep(SESSION_LIMIT_SECONDS)
        await session.aclose()
        ctx.shutdown(reason="Five-minute experiment limit reached")

    expiry = asyncio.create_task(expire_session())

    async def cleanup():
        expiry.cancel()
        await asyncio.gather(expiry, return_exceptions=True)

    ctx.add_shutdown_callback(cleanup)
    await session.generate_reply(
        instructions="Briefly introduce yourself as Voice Debugger. Say this session is voice only, and ask what Python error the user is seeing."
    )


def main():
    settings = load_settings()
    if settings.missing:
        raise SystemExit("Complete these fields in .env first: " + ", ".join(settings.missing))
    # Pass credentials to the worker's child processes, without printing them.
    os.environ["LIVEKIT_URL"] = settings.livekit_url
    os.environ["LIVEKIT_API_KEY"] = settings.livekit_api_key
    os.environ["LIVEKIT_API_SECRET"] = settings.livekit_api_secret
    agents.cli.run_app(server)


if __name__ == "__main__":
    main()
