"""FastAPI application factory."""

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import __version__
from app.api.collectors import Collector, create_collectors_router
from app.browser.chrome import BrowserSessionFactory
from app.settings import Settings


def create_app(
    settings: Settings | None = None,
    browser_factory_builder: Callable[[Settings], BrowserSessionFactory] = BrowserSessionFactory,
    browser_collector: Collector | None = None,
) -> FastAPI:
    runtime_settings = settings if settings is not None else Settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        if runtime_settings.browser_preflight:
            browser_factory_builder(runtime_settings).preflight()
        yield

    app = FastAPI(title="kk-pricewatch-collector", version=__version__, lifespan=lifespan)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    app.include_router(create_collectors_router(runtime_settings, browser_collector))
    return app
