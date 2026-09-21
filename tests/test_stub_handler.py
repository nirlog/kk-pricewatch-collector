import socket

import pytest

from app.contract.v1 import CollectorRequest
from app.handlers.stub import StubCollector


def test_handler_is_callable_without_http_and_never_uses_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def reject_network(*args: object, **kwargs: object) -> None:
        raise AssertionError("stub attempted outbound network access")

    monkeypatch.setattr(socket, "create_connection", reject_network)
    request = CollectorRequest.model_validate(
        {
            "schema_version": "1.0",
            "request_id": "unit",
            "items": [{"id": "x", "url": "ftp://invalid-for-web.invalid/%ZZ"}],
            "options": {
                "stub": {"default": {"type": "success", "price": "10.00", "currency": "RUB"}}
            },
        }
    )
    response = StubCollector().collect(request)
    assert response.success is True
    assert response.items[0].id == "x"
