from fastapi.testclient import TestClient

from app.contract.v1 import CollectorError, CollectorRequest, FailedResponse
from app.main import create_app
from app.settings import Settings


class SpyCollector:
    def __init__(self, raises: bool = False) -> None:
        self.raises = raises
        self.requests: list[CollectorRequest] = []

    def collect(self, request: CollectorRequest):  # type annotation intentionally inferred
        self.requests.append(request)
        if self.raises:
            raise RuntimeError("Authorization: Bearer top-secret")
        return FailedResponse(
            request_id=request.request_id,
            error=CollectorError(code="BROWSER_CONFIGURATION_ERROR", message="Invalid options."),
        )


def payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "request_id": "api-request",
        "items": [{"id": "1", "url": "https://example.com/p"}],
        "options": {"browser": {}},
    }


def test_browser_endpoint_invokes_injected_browser_collector() -> None:
    collector = SpyCollector()
    with TestClient(create_app(Settings(api_token="token"), browser_collector=collector)) as client:
        response = client.post(
            "/api/collectors/browser",
            headers={"Authorization": "Bearer token"},
            json=payload(),
        )
    assert response.status_code == 200
    assert response.json()["error"]["code"] == "BROWSER_CONFIGURATION_ERROR"
    assert collector.requests[0].request_id == "api-request"


def test_auth_and_request_boundary_remain_http_errors() -> None:
    collector = SpyCollector()
    with TestClient(create_app(Settings(api_token="token"), browser_collector=collector)) as client:
        assert client.post("/api/collectors/browser", json=payload()).status_code == 401
        malformed = client.post(
            "/api/collectors/browser",
            headers={"Authorization": "Bearer token", "Content-Type": "application/json"},
            content="{broken",
        )
        assert malformed.status_code == 422


def test_unexpected_collector_error_is_sanitized() -> None:
    with TestClient(
        create_app(Settings(api_token="token"), browser_collector=SpyCollector(raises=True))
    ) as client:
        response = client.post(
            "/api/collectors/browser",
            headers={"Authorization": "Bearer token"},
            json=payload(),
        )
    body = response.json()
    assert response.status_code == 200
    assert body["error"] == {"code": "COLLECTOR_ERROR", "message": "Collector failed."}
    assert "top-secret" not in response.text
