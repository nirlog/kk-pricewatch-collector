import pytest
from pydantic import TypeAdapter, ValidationError

from app.contract.v1 import (
    CollectorError,
    CollectorRequest,
    CollectorResponse,
    FailedItem,
    FailedResponse,
    SuccessfulItem,
    SuccessfulResponse,
)


def valid_request(**updates: object) -> dict[str, object]:
    value: dict[str, object] = {
        "schema_version": "1.0",
        "request_id": " opaque-id ",
        "items": [{"id": "1", "url": " https://example.test/a?z=2&x=%2F "}],
        "options": {},
    }
    value.update(updates)
    return value


def test_request_preserves_opaque_strings_and_accepts_empty_options() -> None:
    request = CollectorRequest.model_validate(valid_request())
    assert request.request_id == " opaque-id "
    assert request.items[0].url == " https://example.test/a?z=2&x=%2F "
    assert request.options == {}


@pytest.mark.parametrize(
    "updates",
    [
        {"schema_version": "2.0"},
        {"request_id": ""},
        {"request_id": " \t"},
        {"items": {}},
        {"items": []},
        {"items": [[]]},
        {"items": [{"id": "", "url": "https://example.test"}]},
        {"items": [{"id": "1", "url": ""}]},
        {"items": [{"id": "1", "url": "u"}, {"id": "1", "url": "v"}]},
        {"options": []},
        {"unexpected": True},
        {"items": [{"id": "1", "url": "u", "unexpected": True}]},
    ],
)
def test_invalid_request_shapes_are_rejected(updates: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        CollectorRequest.model_validate(valid_request(**updates))


@pytest.mark.parametrize("price", ["-1", "+1", "1,20", "1 000", "NaN", "Infinity", 1.2])
def test_invalid_money_is_rejected(price: object) -> None:
    with pytest.raises(ValidationError):
        SuccessfulItem(id="1", price=price, currency="RUB")


@pytest.mark.parametrize("price", ["0", "0.00", "1", "12345.67"])
def test_valid_money_remains_a_string(price: str) -> None:
    assert SuccessfulItem(id="1", price=price, currency="RUB").price == price


@pytest.mark.parametrize("currency", ["rub", "US", "USDD", "12A"])
def test_invalid_currency_is_rejected(currency: str) -> None:
    with pytest.raises(ValidationError):
        SuccessfulItem(id="1", price="1", currency=currency)


@pytest.mark.parametrize("code", ["lower", "BAD-CODE", "", "A" * 65])
def test_invalid_error_code_is_rejected(code: str) -> None:
    with pytest.raises(ValidationError):
        CollectorError(code=code, message="message")


@pytest.mark.parametrize("message", ["", "  ", "x" * 4097])
def test_invalid_error_message_is_rejected(message: str) -> None:
    with pytest.raises(ValidationError):
        CollectorError(code="ERROR", message=message)


def test_typed_response_variants_make_field_conflicts_impossible() -> None:
    adapter = TypeAdapter(CollectorResponse)
    success = SuccessfulResponse(
        request_id="id", items=[SuccessfulItem(id="1", price="1.00", currency="USD")]
    )
    failure = FailedResponse(request_id="id", error=CollectorError(code="FAILED", message="Failed"))
    assert adapter.validate_python(success).success is True
    assert adapter.validate_python(failure).items == []

    with pytest.raises(ValidationError):
        SuccessfulItem.model_validate(
            {"id": "1", "success": True, "price": "1", "currency": "USD", "error": {}}
        )
    with pytest.raises(ValidationError):
        FailedItem.model_validate(
            {
                "id": "1",
                "success": False,
                "error": {"code": "FAILED", "message": "Failed"},
                "price": "1",
            }
        )
