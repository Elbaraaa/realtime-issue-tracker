from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import auth, comments, issues, projects


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Realtime Issue Tracker", version="0.1.0")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    api = APIRouter(prefix="/api")
    for module in (auth, projects, issues, comments):
        api.include_router(module.router)
    app.include_router(api)

    @app.get("/healthz", include_in_schema=False)
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    return app


app = create_app()
