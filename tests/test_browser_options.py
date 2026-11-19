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


@pytest.mark.parametrize(
    "action",
    [
        {"type": "click", "by": "css", "selector": "#accept", "required": False},
        {"type": "wait_for", "by": "xpath", "selector": "//main", "state": "present"},
        {"type": "wait_for", "by": "css", "selector": ".dialog", "state": "visible"},
        {"type": "wait_for", "by": "css", "selector": ".overlay", "state": "hidden"},
    ],
)
def test_valid_browser_actions(action: dict[str, object]) -> None:
    raw = valid_options()
    raw["actions"] = [action]
    options = BrowserCollectorOptions.model_validate(raw)
    assert len(options.actions) == 1
    assert options.actions[0].timeout_seconds == 5


def test_actions_are_optional_and_may_be_empty() -> None:
    assert BrowserCollectorOptions.model_validate(valid_options()).actions == []
    raw = valid_options()
    raw["actions"] = []
    assert BrowserCollectorOptions.model_validate(raw).actions == []


@pytest.mark.parametrize(
    "action",
    [
        {"type": "navigate", "by": "css", "selector": "a"},
        {"type": "click", "by": "id", "selector": "accept"},
        {"type": "click", "by": "css", "selector": "   "},
        {"type": "click", "by": "css", "selector": "x", "timeout_seconds": 0},
        {"type": "click", "by": "css", "selector": "x", "timeout_seconds": 31},
        {"type": "click", "by": "css", "selector": "x", "required": 1},
        {"type": "click", "by": "css", "selector": "x", "extra": True},
        {"type": "wait_for", "by": "css", "selector": "x", "state": "enabled"},
    ],
)
def test_invalid_browser_actions(action: dict[str, object]) -> None:
    raw = valid_options()
    raw["actions"] = [action]
    with pytest.raises(ValidationError):
        BrowserCollectorOptions.model_validate(raw)


def test_action_count_and_total_timeout_are_limited() -> None:
    raw = valid_options()
    raw["actions"] = [{"type": "click", "by": "css", "selector": "x"}] * 11
    with pytest.raises(ValidationError):
        BrowserCollectorOptions.model_validate(raw)

    raw["actions"] = [
        {"type": "click", "by": "css", "selector": str(index), "timeout_seconds": 21}
        for index in range(3)
    ]
    with pytest.raises(ValidationError):
        BrowserCollectorOptions.model_validate(raw)
