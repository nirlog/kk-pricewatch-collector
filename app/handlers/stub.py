"""Deterministic collector used for protocol integration testing."""

from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, ValidationError

from app.contract.v1 import (
    CollectorError,
    CollectorRequest,
    CollectorResponse,
    CurrencyCode,
    ErrorCode,
    ErrorMessage,
    FailedItem,
    FailedResponse,
    PriceString,
    StrictModel,
    SuccessfulItem,
    SuccessfulResponse,
)


class StubSuccess(StrictModel):
    type: Literal["success"]
    price: PriceString
    currency: CurrencyCode


class StubError(StrictModel):
    type: Literal["error"]
    code: ErrorCode
    message: ErrorMessage


StubResult = Annotated[StubSuccess | StubError, Field(discriminator="type")]


class StubConfiguration(StrictModel):
    default: StubResult | None = None
    results: dict[str, StubResult] = Field(default_factory=dict)
    global_error: CollectorError | None = None


class StubCollector:
    """Build responses from options only; no network client is used or accepted."""

    _configuration_error = CollectorError(
        code="STUB_CONFIGURATION_ERROR",
        message="Stub collector configuration is missing or invalid.",
    )

    def collect(self, request: CollectorRequest) -> CollectorResponse:
        try:
            raw_stub = request.options.get("stub")
            configuration = StubConfiguration.model_validate(raw_stub)
        except (ValidationError, TypeError):
            return self._failure(request.request_id, self._configuration_error)

        if configuration.global_error is not None:
            return self._failure(request.request_id, configuration.global_error)

        results: list[SuccessfulItem | FailedItem] = []
        for item in request.items:
            result = configuration.results.get(item.id, configuration.default)
            if result is None:
                return self._failure(request.request_id, self._configuration_error)
            if isinstance(result, StubSuccess):
                results.append(
                    SuccessfulItem(id=item.id, price=result.price, currency=result.currency)
                )
            else:
                results.append(
                    FailedItem(
                        id=item.id,
                        error=CollectorError(code=result.code, message=result.message),
                    )
                )

        return SuccessfulResponse(request_id=request.request_id, items=results)

    @staticmethod
    def _failure(request_id: str, error: CollectorError) -> FailedResponse:
        return FailedResponse(request_id=request_id, error=error)


# Ensures the exported union remains constructible/validatable for downstream users.
collector_response_adapter: TypeAdapter[CollectorResponse] = TypeAdapter(CollectorResponse)
