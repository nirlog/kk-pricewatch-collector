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


class StubItemConfiguration(StrictModel):
    default: StubResult | None = None
    results: dict[str, StubResult] = Field(default_factory=dict)


class StubCollector:
    """Build responses from options only; no network client is used or accepted."""

    _configuration_error = CollectorError(
        code="STUB_CONFIGURATION_ERROR",
        message="Stub collector configuration is missing or invalid.",
    )

    def collect(self, request: CollectorRequest) -> CollectorResponse:
        raw_stub = request.options.get("stub")
        if not isinstance(raw_stub, dict) or not set(raw_stub).issubset(
            {"default", "results", "global_error"}
        ):
            return self._failure(request.request_id, self._configuration_error)

        # A valid global error takes precedence over item configuration. Validate it
        # independently so deliberately malformed default/results values are ignored.
        if "global_error" in raw_stub:
            try:
                global_error = CollectorError.model_validate(raw_stub["global_error"])
            except (ValidationError, TypeError):
                return self._failure(request.request_id, self._configuration_error)
            return self._failure(request.request_id, global_error)

        try:
            configuration = StubItemConfiguration.model_validate(raw_stub)
        except (ValidationError, TypeError):
            return self._failure(request.request_id, self._configuration_error)

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
