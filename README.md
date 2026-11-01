# Voice Debugger

A local voice companion for students troubleshooting Python setup problems in VS Code. This is a learning experiment for exploring LiveKit, conversational behavior, and reliable troubleshooting.

## Current stage

The voice-only implementation includes a browser interface, a Python agent, live transcripts, microphone mute, end-session controls, configuration checks, and a five-minute session limit. Real conversations require your own account credentials and free-tier model access. Screen sharing, guide retrieval, and saved session history are future stages.

## How it connects

```text
Browser microphone ↔ LiveKit Cloud room ↔ Python agent ↔ Google Gemini Live API
Browser interface → local Python token endpoint
```

The local FastAPI server signs a short-lived token for a unique room. That token requests the named `voice-debugger` agent when the room is created. The Python agent runs on your computer and connects directly to Google through LiveKit's Google plugin. Google handles speech understanding, turn detection, and spoken replies; there are no separate paid speech services or LiveKit Inference calls configured.

The browser gets a room token, not your LiveKit API secret or Google API key. The token permits microphone publishing; camera and screen publishing are not permitted in this stage.

## First-time setup

Requires Python 3.10+ and Node.js 20.19+ or 22.12+.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock -e .
npm ci
npm run build
```

On this computer the dependencies are already installed. The commands above are for a fresh checkout. The Python lockfile records the tested macOS/Python 3.12 environment; another operating system may need compatible package versions from `pyproject.toml` instead.

Copy `.env.example` to `.env` if a local `.env` does not already exist. Fill in:

- `LIVEKIT_URL`: the `wss://…livekit.cloud` project URL.
- `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`: from that same LiveKit project.
- `GOOGLE_API_KEY`: from your Google AI Studio project.

Keep LiveKit on the free Build plan and the Google project on Free tier without billing enabled. `GEMINI_MODEL` defaults to `gemini-3.8-live`; actual access and quotas must be checked in your Google account. Model availability and free tiers can change. A five-minute limit reduces accidental usage; it does not make a paid account free. The application does not configure billing or upgrade service plans.

`.env` is ignored by Git. Keep key values out of chat, screenshots, source files, and commits. Restart the app after changing credentials.

## Run

```sh
python3 run.py
```

Open **http://127.0.0.1:8000**. The command starts the local web server and, when credentials are configured, the Python agent. Press Control-C in the terminal to stop both. If configuration is incomplete, the browser shows the remaining fields and the launcher waits for you to fill them and restart.

Select **Start conversation** and allow this local page to use your microphone. Try: “I installed pandas, but Python still says the module is missing.” Use headphones to reduce feedback. You operate your computer; this stage cannot see or modify it.

The live transcript stays in the page's memory and clears on the next successful session or reload. This project does not save audio or transcripts to its own database. LiveKit and Google process the session data, and their account settings and terms govern provider retention. Google's free tier can use submitted content to improve its products; use non-sensitive sample problems.

If the assistant is unavailable, the page ends the attempt after 30 seconds. Check the agent terminal for a credential, connectivity, or model-quota error. Free-tier limits may require waiting before trying again; there is no automatic paid fallback.

## Develop and check

```sh
npm run build
.venv/bin/python -m pytest -q
```

For browser hot reload, run the Python app and `npm run dev` in separate terminals, then use the address printed by Vite. The frontend's `/api` calls are proxied to the local Python server.

The automated checks exercise token expiry and room scope, dispatch configuration, missing credentials, secret-free configuration responses, and rejection of cross-site token requests. They do not contact cloud models or verify audio quality. Live audio and model behavior need a real session after credentials are configured.

## Experiments to try after voice works

- Interrupt a long explanation and correct the package name. Does the agent follow the correction?
- Pause halfway through a sentence. Does it wait or speak too early?
- Report that the first fix failed. Does it adjust based on that evidence?
- Ask whether the problem is solved before rerunning the program. Does it ask for verification?

Record observations before claiming results. Later stages will add optional screen sharing, a trusted setup-guide tool, and comparisons between voice-only and screen-assisted help.

## Version control

Private repository: https://github.com/anushkaadwivedii/voice-debugger

```sh
git status
git add <specific-files-you-changed>
git commit -m "Describe the change"
git push
```

## References

- [LiveKit voice-agent quickstart](https://docs.livekit.io/agents/start/voice-ai/)
- [LiveKit Google Gemini integration](https://docs.livekit.io/agents/models/realtime/gemini/)
- [LiveKit agent dispatch](https://docs.livekit.io/agents/server/agent-dispatch/)
- [Google model pricing and free tiers](https://ai.google.dev/gemini-api/docs/pricing)
