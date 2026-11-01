"""Local web server and narrowly scoped LiveKit token endpoint."""

from datetime import timedelta
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from livekit import api
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import AGENT_NAME, ROOT, SESSION_LIMIT_SECONDS, Settings, load_settings

LOCAL_ORIGINS = {
    f"http://{host}:{port}"
    for host in ("127.0.0.1", "localhost")
    for port in (8000, 5173)
}


def create_app(settings_loader=load_settings) -> FastAPI:
    app = FastAPI(title="Voice Debugger", docs_url=None, redoc_url=None, openapi_url=None)
    app.add_middleware(
        TrustedHostMiddleware, allowed_hosts=["127.0.0.1", "localhost", "testserver"]
    )

    @app.middleware("http")
    async def local_requests(request: Request, call_next):
        origin = request.headers.get("origin")
        if request.method == "POST" and origin and origin not in LOCAL_ORIGINS:
            return JSONResponse({"detail": "Open Voice Debugger from its local address."}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

    @app.get("/api/config")
    def config():
        settings: Settings = settings_loader()
        missing = settings.missing
        return {
            "configured": not missing,
            "missing": missing,
            "model": settings.model,
            "sessionLimitSeconds": SESSION_LIMIT_SECONDS,
        }

    @app.post("/api/session")
    def session():
        settings: Settings = settings_loader()
        if settings.missing:
            raise HTTPException(503, detail={"message": "Finish the local account setup first.", "missing": settings.missing})
        room_name = f"voice-debugger-{uuid4().hex}"
        identity = f"student-{uuid4().hex}"
        token = (
            api.AccessToken(settings.livekit_api_key, settings.livekit_api_secret)
            .with_identity(identity)
            .with_name("You")
            .with_ttl(timedelta(minutes=10))
            .with_grants(api.VideoGrants(
                room_join=True, room=room_name, can_publish=True,
                can_subscribe=True, can_publish_data=True,
                can_publish_sources=["microphone"],
            ))
            .with_room_config(api.RoomConfiguration(
                agents=[api.RoomAgentDispatch(agent_name=AGENT_NAME)],
                empty_timeout=30, departure_timeout=10,
            ))
            .to_jwt()
        )
        return {"url": settings.livekit_url, "token": token, "sessionLimitSeconds": SESSION_LIMIT_SECONDS}

    dist = ROOT / "dist"
    if dist.is_dir():
        app.mount("/", StaticFiles(directory=dist, html=True), name="browser")
    else:
        @app.get("/")
        def build_required():
            return JSONResponse({"message": "Build the browser interface with npm run build."}, status_code=503)
    return app


app = create_app()


def main():
    import uvicorn
    uvicorn.run("voice_debugger.server:app", host="127.0.0.1", port=8000, access_log=False)


if __name__ == "__main__":
    main()
