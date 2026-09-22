import pytest
from pydantic import ValidationError

from app.collectors.options import BrowserCollectorOptions


def valid_options() -> dict[str, object]:
    return {
        "allowed_hosts": ["Example.COM"],
        "price": {"by": "css", "selector": ".price", "source": "text"},
        "currency": "RUB",
        "decimal_separator": "none",
    }


def test_valid_text_xpath_and_attribute_options() -> None:
    options = BrowserCollectorOptions.model_validate(valid_options())
    assert options.allowed_hosts == ["example.com"]
    assert options.wait_timeout_seconds == 15
    xpath = valid_options()
    xpath["price"] = {"by": "xpath", "selector": "//span", "source": "text"}
    assert BrowserCollectorOptions.model_validate(xpath).price.by == "xpath"
    attribute = valid_options()
    attribute["price"] = {
        "by": "css",
        "selector": "meta[itemprop='price']",
        "source": "attribute",
        "attribute": "content",
    }
    assert BrowserCollectorOptions.model_validate(attribute).price.attribute == "content"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("allowed_hosts", []),
        ("allowed_hosts", [""]),
        ("allowed_hosts", ["EXAMPLE.com", "example.COM"]),
        ("currency", "rub"),
        ("decimal_separator", "auto"),
        ("wait_timeout_seconds", 0),
        ("wait_timeout_seconds", 61),
        ("page_load_timeout_seconds", 121),
    ],
)
def test_invalid_option_values(field: str, value: object) -> None:
    raw = valid_options()
    raw[field] = value
    with pytest.raises(ValidationError):
        BrowserCollectorOptions.model_validate(raw)


@pytest.mark.parametrize(
    "price",
    [
        {"by": "id", "selector": "price", "source": "text"},
        {"by": "css", "selector": ".price", "source": "html"},
        {"by": "css", "selector": ".price", "source": "attribute"},
        {"by": "css", "selector": ".price", "source": "text", "attribute": "value"},
    ],
)
def test_invalid_price_options(price: dict[str, str]) -> None:
    raw = valid_options()
    raw["price"] = price
    with pytest.raises(ValidationError):
        BrowserCollectorOptions.model_validate(raw)


def test_unknown_fields_are_rejected() -> None:
    raw = valid_options()
    raw["unexpected"] = True
    with pytest.raises(ValidationError):
        BrowserCollectorOptions.model_validate(raw)
