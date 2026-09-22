"""Strict options for the generic browser collector."""

import ipaddress
from typing import Annotated, Literal, Self

from pydantic import Field, StrictBool, StringConstraints, field_validator, model_validator

from app.contract.v1 import CurrencyCode, StrictModel

Selector = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=2048)]
AttributeName = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=256)]
ActionTimeout = Annotated[int, Field(strict=True, ge=1, le=30)]


class ClickAction(StrictModel):
    type: Literal["click"]
    by: Literal["css", "xpath"]
    selector: Selector
    timeout_seconds: ActionTimeout = 5
    required: StrictBool = True

    @field_validator("selector")
    @classmethod
    def reject_blank_selector(cls, selector: str) -> str:
        if not selector.strip():
            raise ValueError("selector must not be blank")
        return selector


class WaitForAction(StrictModel):
    type: Literal["wait_for"]
    by: Literal["css", "xpath"]
    selector: Selector
    state: Literal["present", "visible", "hidden"]
    timeout_seconds: ActionTimeout = 5
    required: StrictBool = True

    @field_validator("selector")
    @classmethod
    def reject_blank_selector(cls, selector: str) -> str:
        if not selector.strip():
            raise ValueError("selector must not be blank")
        return selector


BrowserAction = Annotated[ClickAction | WaitForAction, Field(discriminator="type")]


class PriceSelector(StrictModel):
    by: Literal["css", "xpath"]
    selector: Selector
    source: Literal["text", "attribute"]
    attribute: AttributeName | None = None

    @model_validator(mode="after")
    def validate_source(self) -> Self:
        if not self.selector.strip():
            raise ValueError("selector must not be blank")
        if self.source == "attribute" and (self.attribute is None or not self.attribute.strip()):
            raise ValueError("attribute is required for attribute source")
        if self.source == "text" and self.attribute is not None:
            raise ValueError("attribute is forbidden for text source")
        return self


class BrowserCollectorOptions(StrictModel):
    allowed_hosts: list[str] = Field(min_length=1)
    price: PriceSelector
    currency: CurrencyCode
    decimal_separator: Literal["none", "dot", "comma"]
    wait_timeout_seconds: int = Field(default=15, ge=1, le=60)
    page_load_timeout_seconds: int = Field(default=30, ge=1, le=120)
    actions: list[BrowserAction] = Field(default_factory=list, max_length=10)

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_hosts(cls, hosts: list[str]) -> list[str]:
        normalized: list[str] = []
        for host in hosts:
            if not isinstance(host, str) or not host.strip():
                raise ValueError("allowed hosts must be non-empty strings")
            value = host.strip().lower()
            if any(character in value for character in "*/@[]") or value.startswith("."):
                raise ValueError("allowed hosts must be exact hostnames")
            if ":" in value:
                try:
                    ipaddress.IPv6Address(value)
                except ValueError as exc:
                    raise ValueError("allowed hosts must be exact hostnames") from exc
            normalized.append(value.rstrip("."))
        if len(normalized) != len(set(normalized)):
            raise ValueError("allowed hosts must be unique")
        return normalized

    @model_validator(mode="after")
    def validate_action_timeout_budget(self) -> Self:
        if sum(action.timeout_seconds for action in self.actions) > 60:
            raise ValueError("total action timeout must not exceed 60 seconds")
        return self
