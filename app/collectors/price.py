"""Deterministic Decimal price normalization without floating point."""

from decimal import Decimal, InvalidOperation
from typing import Literal


class PriceParseError(ValueError):
    """The selected value does not contain one unambiguous price."""


def parse_price(raw: str, decimal_separator: Literal["none", "dot", "comma"]) -> str:
    token = _first_numeric_token(raw)
    decimal_mark = {"none": None, "dot": ".", "comma": ","}[decimal_separator]
    grouping_marks = {" ", "\u00a0", "\u202f", ",", "."}
    if decimal_mark is not None:
        grouping_marks.remove(decimal_mark)

    if decimal_mark is not None and token.count(decimal_mark) > 1:
        raise PriceParseError("price has multiple decimal separators")
    parts = token.split(decimal_mark) if decimal_mark is not None else [token]
    if len(parts) == 2 and (not parts[0] or not parts[1] or not parts[1].isdigit()):
        raise PriceParseError("price has an invalid decimal part")

    integer = _normalize_integer(parts[0], grouping_marks)
    normalized = integer if len(parts) == 1 else f"{integer}.{parts[1]}"
    try:
        Decimal(normalized)
    except InvalidOperation as exc:
        raise PriceParseError("price is invalid") from exc
    return normalized


def _first_numeric_token(raw: str) -> str:
    start = next((index for index, character in enumerate(raw) if character in "0123456789"), None)
    if start is None:
        raise PriceParseError("price was not found")
    accepted = set("0123456789., \u00a0\u202f")
    end = start
    while end < len(raw) and raw[end] in accepted:
        end += 1
    token = raw[start:end].rstrip(" \u00a0\u202f")
    if not token:
        raise PriceParseError("price was not found")
    return token


def _normalize_integer(value: str, grouping_marks: set[str]) -> str:
    used = {character for character in value if character in grouping_marks}
    if any(not (character in "0123456789" or character in grouping_marks) for character in value):
        raise PriceParseError("price contains invalid characters")
    # Different whitespace code points are one grouping style; punctuation may not be mixed.
    styles = {"space" if character.isspace() else character for character in used}
    if len(styles) > 1:
        raise PriceParseError("price has ambiguous grouping separators")
    if not styles:
        if not value.isdigit():
            raise PriceParseError("price is invalid")
        return value
    groups: list[str] = []
    current = ""
    for character in value:
        if character in "0123456789":
            current += character
        else:
            groups.append(current)
            current = ""
    groups.append(current)
    if not groups[0] or len(groups[0]) > 3 or any(len(group) != 3 for group in groups[1:]):
        raise PriceParseError("price has malformed grouping")
    return "".join(groups)
