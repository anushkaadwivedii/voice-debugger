"""Read secrets on the Python side only; never return their values to the browser."""

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]
AGENT_NAME = "voice-debugger"
SESSION_LIMIT_SECONDS = 300


@dataclass(frozen=True)
class Settings:
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""
    google_api_key: str = ""
    model: str = "gemini-3.8-live"

    @property
    def missing(self) -> list[str]:
        fields = {
            "LIVEKIT_URL": self.livekit_url,
            "LIVEKIT_API_KEY": self.livekit_api_key,
            "LIVEKIT_API_SECRET": self.livekit_api_secret,
            "GOOGLE_API_KEY": self.google_api_key,
        }
        missing = [
            name for name, value in fields.items()
            if not value or value.lower().startswith(("your_", "replace", "paste", "<"))
        ]
        parsed = urlparse(self.livekit_url)
        if "LIVEKIT_URL" not in missing and (
            parsed.scheme != "wss" or not parsed.hostname
            or not parsed.hostname.endswith(".livekit.cloud")
            or parsed.username or parsed.password
        ):
            missing.append("LIVEKIT_URL")
        return missing


def load_settings() -> Settings:
    # The project's explicit settings take priority over unrelated shell credentials.
    values = {**os.environ, **dotenv_values(ROOT / ".env")}

    def value(name: str, default: str = "") -> str:
        return str(values.get(name) or default).strip()

    return Settings(
        livekit_url=value("LIVEKIT_URL"),
        livekit_api_key=value("LIVEKIT_API_KEY"),
        livekit_api_secret=value("LIVEKIT_API_SECRET"),
        google_api_key=value("GOOGLE_API_KEY"),
        model=value("GEMINI_MODEL", "gemini-3.8-live"),
    )
