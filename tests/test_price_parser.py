from decimal import Decimal

import pytest

from app.collectors.price import PriceParseError, parse_price


@pytest.mark.parametrize(
    ("raw", "separator", "expected"),
    [
        ("129 990 ₽", "none", "129990"),
        ("129\u00a0990 ₽", "none", "129990"),
        ("129\u202f990 ₽", "none", "129990"),
        ("Price: 129990 RUB", "none", "129990"),
        ("129 990,50 ₽", "comma", "129990.50"),
        ("129,990.50 USD", "dot", "129990.50"),
    ],
)
def test_price_normalization(raw: str, separator: str, expected: str) -> None:
    result = parse_price(raw, separator)  # type: ignore[arg-type]
    assert result == expected
    assert Decimal(result) == Decimal(expected)


@pytest.mark.parametrize(
    ("raw", "separator"),
    [
        ("no price", "none"),
        ("12 34", "none"),
        ("1,2,3", "comma"),
        ("12.34.56", "dot"),
        ("12,345.67", "comma"),
        ("12.", "dot"),
    ],
)
def test_malformed_prices_are_rejected(raw: str, separator: str) -> None:
    with pytest.raises(PriceParseError):
        parse_price(raw, separator)  # type: ignore[arg-type]
