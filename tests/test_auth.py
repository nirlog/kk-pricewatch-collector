from fastapi.testclient import TestClient

TOKEN = "unit-test-token"


def test_valid_bearer_token_is_accepted(
    client: TestClient, auth_headers: dict[str, str], minimal_payload: dict[str, object]
) -> None:
    assert (
        client.post(
            "/api/collectors/browser", headers=auth_headers, json=minimal_payload
        ).status_code
        == 200
    )


def test_authentication_failures_are_safe(
    client: TestClient, minimal_payload: dict[str, object]
) -> None:
    credentials = [None, "Basic value", "Bearer ", "Bearer supplied-secret"]
    for credential in credentials:
        headers = {} if credential is None else {"Authorization": credential}
        response = client.post("/api/collectors/browser", headers=headers, json=minimal_payload)
        assert response.status_code == 401
        assert response.headers["www-authenticate"] == "Bearer"
        body = response.text
        assert "supplied-secret" not in body
        assert TOKEN not in body
