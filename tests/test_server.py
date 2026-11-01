from dataclasses import replace
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from livekit.api import TokenVerifier

from voice_debugger.config import Settings
from voice_debugger.server import create_app

SETTINGS = Settings(
    livekit_url="wss://example.livekit.cloud",
    livekit_api_key="APItestkey",
    livekit_api_secret="test-secret-that-is-at-least-thirty-two-characters",
    google_api_key="test-google-key-not-a-real-credential",
)


def test_missing_credentials_never_issue_a_token():
    client = TestClient(create_app(lambda: Settings()))
    response = client.post("/api/session")
    assert response.status_code == 503
    assert "token" not in response.json()
    assert len(response.json()["detail"]["missing"]) == 4


def test_token_is_room_scoped_short_lived_and_dispatches_the_right_agent():
    client = TestClient(create_app(lambda: SETTINGS))
    first = client.post("/api/session")
    second = client.post("/api/session")
    assert first.status_code == 200
    verifier = TokenVerifier(SETTINGS.livekit_api_key, SETTINGS.livekit_api_secret)
    claims = verifier.verify(first.json()["token"])
    other = verifier.verify(second.json()["token"])
    assert claims.video.room_join
    assert claims.video.room != other.video.room
    assert claims.identity != other.identity
    assert not claims.video.room_admin
    assert claims.video.can_publish_sources == ["microphone"]
    assert claims.room_config.agents[0].agent_name == "voice-debugger"
    assert first.json()["sessionLimitSeconds"] == 300
    import jwt
    raw = jwt.decode(first.json()["token"], SETTINGS.livekit_api_secret, algorithms=["HS256"], issuer=SETTINGS.livekit_api_key)
    remaining = raw["exp"] - datetime.now(timezone.utc).timestamp()
    assert 570 < remaining <= 600


def test_config_exposes_status_but_not_secrets():
    response = TestClient(create_app(lambda: SETTINGS)).get("/api/config")
    assert response.json()["configured"]
    for secret in (SETTINGS.google_api_key, SETTINGS.livekit_api_secret, SETTINGS.livekit_api_key):
        assert secret not in response.text
    assert response.headers["cache-control"] == "no-store"


def test_cross_site_token_requests_and_untrusted_hosts_are_rejected():
    client = TestClient(create_app(lambda: SETTINGS))
    assert client.post("/api/session", headers={"Origin": "https://unrelated.example"}).status_code == 403
    assert client.post("/api/session", headers={"Origin": "http://127.0.0.1:8000"}).status_code == 200
    assert client.get("/api/config", headers={"Host": "unrelated.example"}).status_code == 400


def test_placeholder_and_invalid_urls_are_reported_as_setup_problems():
    settings = replace(SETTINGS, livekit_url="https://example.livekit.cloud", google_api_key="your_google_key")
    assert set(settings.missing) == {"LIVEKIT_URL", "GOOGLE_API_KEY"}
