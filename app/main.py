"""FastAPI application factory."""

from fastapi import FastAPI

from app import __version__
from app.api.collectors import create_collectors_router
from app.settings import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    runtime_settings = settings if settings is not None else Settings()
    app = FastAPI(title="kk-pricewatch-collector", version=__version__)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_collectors_router(runtime_settings))
    return app
