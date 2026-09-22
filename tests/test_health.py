from fastapi.testclient import TestClient


def test_health_is_public_and_minimal(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    assert set(response.json()) == {"status"}


def test_collector_endpoint_still_requires_authentication(
    client: TestClient, minimal_payload: dict[str, object]
) -> None:
    response = client.post("/api/collectors/browser", json=minimal_payload)
    assert response.status_code == 401
