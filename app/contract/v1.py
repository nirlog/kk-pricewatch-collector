"""Strict, framework-independent models for collector protocol 1.0."""

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

NonEmptyString = Annotated[str, StringConstraints(strict=True, min_length=1)]
PriceString = Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9]+(?:\.[0-9]+)?$")]
CurrencyCode = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z]{3}$")]
ErrorCode = Annotated[str, StringConstraints(strict=True, pattern=r"^[A-Z0-9_]{1,64}$")]
ErrorMessage = Annotated[str, StringConstraints(strict=True, min_length=1, max_length=4096)]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class CollectorItemRequest(StrictModel):
    id: NonEmptyString
    url: NonEmptyString

    @model_validator(mode="after")
    def reject_blank_values(self) -> "CollectorItemRequest":
        if not self.id.strip():
            raise ValueError("item id must not be blank")
        if not self.url.strip():
            raise ValueError("item url must not be blank")
        return self


class CollectorRequest(StrictModel):
    schema_version: Literal["1.0"]
    request_id: NonEmptyString
    items: list[CollectorItemRequest] = Field(min_length=1)
    options: dict[str, Any]

    @model_validator(mode="after")
    def validate_request(self) -> "CollectorRequest":
        if not self.request_id.strip():
            raise ValueError("request_id must not be blank")
        ids = [item.id for item in self.items]
        if len(ids) != len(set(ids)):
            raise ValueError("item ids must be unique")
        return self


class CollectorError(StrictModel):
    code: ErrorCode
    message: ErrorMessage

    @model_validator(mode="after")
    def reject_blank_message(self) -> "CollectorError":
        if not self.message.strip():
            raise ValueError("error message must not be blank")
        return self


class SuccessfulItem(StrictModel):
    id: NonEmptyString
    success: Literal[True] = True
    price: PriceString
    currency: CurrencyCode


class FailedItem(StrictModel):
    id: NonEmptyString
    success: Literal[False] = False
    error: CollectorError


CollectorItemResponse = Annotated[SuccessfulItem | FailedItem, Field(discriminator="success")]


class SuccessfulResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: NonEmptyString
    success: Literal[True] = True
    items: list[CollectorItemResponse]


class FailedResponse(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    request_id: NonEmptyString
    success: Literal[False] = False
    items: list[CollectorItemResponse] = Field(default_factory=list, max_length=0)
    error: CollectorError


CollectorResponse = Annotated[SuccessfulResponse | FailedResponse, Field(discriminator="success")]
