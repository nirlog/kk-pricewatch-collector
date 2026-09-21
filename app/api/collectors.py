"""Collector HTTP routes."""

from typing import Annotated

from fastapi import APIRouter, Depends, Header

from app.contract.v1 import CollectorError, CollectorRequest, CollectorResponse, FailedResponse
from app.handlers.stub import StubCollector
from app.security.bearer import authenticate_bearer
from app.settings import Settings


def create_collectors_router(settings: Settings) -> APIRouter:
    router = APIRouter(prefix="/api/collectors", tags=["collectors"])
    collector = StubCollector()

    def authenticate(authorization: Annotated[str | None, Depends(_authorization)]) -> None:
        authenticate_bearer(authorization, settings=settings)

    @router.post("/browser", response_model=CollectorResponse, dependencies=[Depends(authenticate)])
    def collect_browser(request: CollectorRequest) -> CollectorResponse:
        try:
            return collector.collect(request)
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
