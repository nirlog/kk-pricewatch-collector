"""Collector HTTP routes."""

from typing import Annotated, Protocol

from fastapi import APIRouter, Depends, Header

from app.browser.chrome import BrowserSessionFactory
from app.collectors.browser import BrowserCollector
from app.contract.v1 import CollectorError, CollectorRequest, CollectorResponse, FailedResponse
from app.security.bearer import authenticate_bearer
from app.settings import Settings


class Collector(Protocol):
    def collect(self, request: CollectorRequest) -> CollectorResponse: ...


def create_collectors_router(settings: Settings, collector: Collector | None = None) -> APIRouter:
    router = APIRouter(prefix="/api/collectors", tags=["collectors"])

    def authenticate(authorization: Annotated[str | None, Depends(_authorization)]) -> None:
        authenticate_bearer(authorization, settings=settings)

    @router.post("/browser", response_model=CollectorResponse, dependencies=[Depends(authenticate)])
    def collect_browser(request: CollectorRequest) -> CollectorResponse:
        try:
            active_collector = (
                collector
                if collector is not None
                else BrowserCollector(BrowserSessionFactory(settings))
            )
            return active_collector.collect(request)
        except Exception:  # pragma: no cover - defensive HTTP boundary
            return FailedResponse(
                request_id=request.request_id,
                error=CollectorError(code="COLLECTOR_ERROR", message="Collector failed."),
            )

    return router


def _authorization(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
) -> str | None:
    return authorization
