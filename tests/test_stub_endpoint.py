from copy import deepcopy

import pytest
from fastapi.testclient import TestClient


def post(
    client: TestClient, headers: dict[str, str], payload: dict[str, object]
):  # type annotation intentionally inferred for TestClient response compatibility
    return client.post("/api/collectors/browser", headers=headers, json=payload)


def test_default_success_round_trips_ids_and_money_string(
    client: TestClient, auth_headers: dict[str, str], minimal_payload: dict[str, object]
) -> None:
    payload = deepcopy(minimal_payload)
    payload["request_id"] = " opaque/request-id "
    response = post(client, auth_headers, payload)
    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "request_id": " opaque/request-id ",
        "success": True,
        "items": [{"id": "12", "success": True, "price": "12345.67", "currency": "RUB"}],
    }
    assert isinstance(response.json()["items"][0]["price"], str)


def test_multiple_items_override_and_order(
    client: TestClient, auth_headers: dict[str, str], minimal_payload: dict[str, object]
) -> None:
    payload = deepcopy(minimal_payload)
    payload["items"] = [
        {"id": "13", "url": "not-even-a-normalized-url?b=2&a=%2F"},
        {"id": "12", "url": "https://example.test/"},
    ]
    payload["options"] = {
        "future_opaque_key": [1, 2],
        "stub": {
            "default": {"type": "success", "price": "9", "currency": "EUR"},
            "results": {
                "13": {
                    "type": "error",
                    "code": "PRICE_NOT_FOUND",
                    "message": "Stub price was not found",
                }
            },
        },
    }
    response = post(client, auth_headers, payload)
    assert response.status_code == 200
    assert response.json()["items"] == [
        {
            "id": "13",
            "success": False,
            "error": {"code": "PRICE_NOT_FOUND", "message": "Stub price was not found"},
        },
        {"id": "12", "success": True, "price": "9", "currency": "EUR"},
    ]


def test_all_items_can_use_overrides_without_default(
    client: TestClient, auth_headers: dict[str, str], minimal_payload: dict[str, object]
) -> None:
    payload = deepcopy(minimal_payload)
    payload["options"] = {
        "stub": {"results": {"12": {"type": "success", "price": "0", "currency": "USD"}}}
    }
    assert post(client, auth_headers, payload).json()["success"] is True


def test_global_error_is_protocol_failure_with_http_200(
    client: TestClient, auth_headers: dict[str, str], minimal_payload: dict[str, object]
) -> None:
    payload = deepcopy(minimal_payload)
    payload["options"] = {
        "stub": {
            "global_error": {"code": "COLLECTOR_ERROR", "message": "Stub global failure"},
            "default": {"type": "success", "price": "1", "currency": "RUB"},
        }
    }
    response = post(client, auth_headers, payload)
    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "request_id": "request-1",
        "success": False,
        "items": [],
        "error": {"code": "COLLECTOR_ERROR", "message": "Stub global failure"},
    }


@pytest.mark.parametrize(
    "ignored_configuration",
    [
        {"default": {"type": "success", "price": -1, "currency": "invalid"}},
        {"results": {"12": {"type": "error", "code": "invalid", "message": ""}}},
    ],
)
def test_valid_global_error_ignores_malformed_item_configuration(
    client: TestClient,
    auth_headers: dict[str, str],
    minimal_payload: dict[str, object],
    ignored_configuration: dict[str, object],
) -> None:
    payload = deepcopy(minimal_payload)
    payload["options"] = {
        "stub": {
            **ignored_configuration,
            "global_error": {"code": "COLLECTOR_ERROR", "message": "Requested failure"},
        }
    }

    response = post(client, auth_headers, payload)

    assert response.status_code == 200
    assert response.json() == {
        "schema_version": "1.0",
        "request_id": "request-1",
        "success": False,
        "items": [],
        "error": {"code": "COLLECTOR_ERROR", "message": "Requested failure"},
    }


def test_malformed_global_error_is_controlled_configuration_failure(
    client: TestClient, auth_headers: dict[str, str], minimal_payload: dict[str, object]
) -> None:
    payload = deepcopy(minimal_payload)
    payload["options"] = {
        "stub": {
            "global_error": {"code": "invalid", "message": ""},
            "default": {"type": "success", "price": "1", "currency": "RUB"},
        }
    }

    response = post(client, auth_headers, payload)

    assert response.status_code == 200
    assert response.json()["error"] == {
        "code": "STUB_CONFIGURATION_ERROR",
        "message": "Stub collector configuration is missing or invalid.",
    }


def test_global_error_does_not_allow_unexpected_stub_fields(
    client: TestClient, auth_headers: dict[str, str], minimal_payload: dict[str, object]
) -> None:
    payload = deepcopy(minimal_payload)
    payload["options"] = {
        "stub": {
            "global_error": {"code": "COLLECTOR_ERROR", "message": "Requested failure"},
            "unexpected": True,
        }
    }

    response = post(client, auth_headers, payload)

    assert response.json()["error"]["code"] == "STUB_CONFIGURATION_ERROR"


@pytest.mark.parametrize(
    "stub",
    [
        None,
        [],
        {},
        {"default": {"type": "success", "price": -1, "currency": "RUB"}},
        {"default": {"type": "success", "price": "1", "currency": "rub"}},
        {"default": {"type": "error", "code": "bad-code", "message": "failed"}},
        {"default": {"type": "error", "code": "FAILED", "message": ""}},
        {"default": {"type": "error", "code": "FAILED", "message": "x" * 4097}},
        {"default": {"type": "unknown"}},
        {"unexpected": True},
    ],
)
def test_missing_or_malformed_stub_is_controlled_failure(
    client: TestClient,
    auth_headers: dict[str, str],
    minimal_payload: dict[str, object],
    stub: object,
) -> None:
    payload = deepcopy(minimal_payload)
    payload["options"] = {} if stub is None else {"stub": stub}
    response = post(client, auth_headers, payload)
    assert response.status_code == 200
    assert response.json()["success"] is False
    assert response.json()["items"] == []
    assert response.json()["error"] == {
        "code": "STUB_CONFIGURATION_ERROR",
        "message": "Stub collector configuration is missing or invalid.",
    }


def test_malformed_json_and_boundary_contract_failures_return_4xx(
    client: TestClient, auth_headers: dict[str, str], minimal_payload: dict[str, object]
) -> None:
    malformed = client.post(
        "/api/collectors/browser",
        headers={**auth_headers, "Content-Type": "application/json"},
        content="{broken",
    )
    assert malformed.status_code == 422
    assert post(client, auth_headers, []).status_code == 422  # type: ignore[arg-type]

    payload = deepcopy(minimal_payload)
    payload["options"] = []
    assert post(client, auth_headers, payload).status_code == 422
