# AGENTS.md

## Project purpose

`kk-pricewatch-collector` is the standalone external collection service for the `kk.pricewatch` 1C-Bitrix module.

The service is an independent product/runtime. It must not depend on Bitrix internals, Bitrix ORM, Bitrix module files, or a shared filesystem with the PHP application.

Its public boundary is the collector HTTP protocol. The initial supported protocol version is `1.0`.

## Runtime and baseline stack

- Python 3.12+
- FastAPI
- Pydantic v2
- Uvicorn for local/runtime serving
- pytest
- Ruff for lint/format checks
- mypy for static typing where practical

Prefer the standard library unless a dependency materially improves correctness, security, or maintainability.

## Architecture

Keep the following concerns separated:

- `api`: HTTP routing, authentication boundary, request/response status handling.
- `contract`: protocol `1.0` request/response models and validation.
- `handlers`: routing from an API endpoint/handler to collection behavior.
- `collectors`: acquisition implementations. Task 001 uses a deterministic stub only.
- `security`: authentication and security-related helpers.
- `settings`: environment/configuration loading and validation.

Business/protocol code must not depend directly on FastAPI request objects when it can operate on typed domain/contract models instead.

## Collector protocol 1.0

The PHP module sends HTTP `POST` requests with JSON shaped as:

```json
{
  "schema_version": "1.0",
  "request_id": "opaque-non-empty-id",
  "items": [
    {
      "id": "12",
      "url": "https://competitor.example/product/1"
    }
  ],
  "options": {}
}
```

Required invariants:

- top-level value is a JSON object;
- `schema_version` must equal `"1.0"`;
- `request_id` is a non-empty string and must be returned unchanged;
- `items` is a JSON list with at least one item;
- item `id` is a non-empty string;
- item IDs are unique within one request;
- item `url` is a non-empty string and must not be normalized/re-written by the protocol layer;
- `options` is a JSON object/map, never a JSON list;
- unknown additional fields should be rejected in Task 001 unless the task specification explicitly says otherwise.

Successful item response:

```json
{
  "id": "12",
  "success": true,
  "price": "129990.00",
  "currency": "RUB"
}
```

Failed item response:

```json
{
  "id": "13",
  "success": false,
  "error": {
    "code": "PRICE_NOT_FOUND",
    "message": "Price was not found"
  }
}
```

Global success response:

```json
{
  "schema_version": "1.0",
  "request_id": "opaque-non-empty-id",
  "success": true,
  "items": []
}
```

Global failure response:

```json
{
  "schema_version": "1.0",
  "request_id": "opaque-non-empty-id",
  "success": false,
  "items": [],
  "error": {
    "code": "COLLECTOR_ERROR",
    "message": "Collector failed"
  }
}
```

Protocol-level global failures are returned as valid protocol JSON. Unless a task explicitly changes this, use HTTP 200 for protocol-level collector failures; HTTP 4xx/5xx are reserved for HTTP/authentication/request-boundary failures.

## Money and error validation

Never represent money as `float`.

For protocol output:

- `price` is a decimal string accepted by the PHP `kk.pricewatch` contract;
- `currency` is an uppercase 3-letter code such as `RUB`;
- error `code` must match `^[A-Z0-9_]{1,64}$`;
- error `message` must be a non-empty string with a reasonable maximum length (4096 characters unless a task specifies another limit).

## Authentication and secrets

External collector requests use:

```text
Authorization: Bearer <token>
```

Rules:

- never put the API token in URLs or query strings;
- never echo the token in JSON responses;
- never include the token in exception text or logs;
- never include request Authorization headers in structured logs;
- do not expose secrets through debug endpoints;
- use constant-time comparison for configured bearer-token validation where applicable;
- `.env` files containing real secrets must never be committed;
- `.env.example` may contain names/defaults only, never real credentials.

## Handler semantics

The Bitrix module selects collection behavior through the request path (`COLLECTOR_HANDLER` on the PHP side), for example:

```text
POST /api/collectors/browser
```

Do not add `handler`, `competitor_id`, `product_id`, `site_id`, or bearer secrets to protocol body `1.0`.

The service should remain reusable independently of the Bitrix database.

## Testing

Tests must be deterministic and must not require internet access.

Every task should add tests for its public behavior. For protocol/authentication work, cover at minimum:

- valid requests;
- malformed JSON;
- wrong/missing schema version;
- wrong JSON container types;
- duplicate item IDs;
- invalid response money/currency/error shapes where applicable;
- authentication success/failure;
- secret non-disclosure;
- request ID round-trip;
- mixed per-item success/failure.

Do not make real competitor-network calls in unit tests.

## Quality gates

Before opening or updating a PR, run the maximum available set of:

```bash
python -m pytest
ruff check .
ruff format --check .
mypy app
```

If a command cannot run because of the execution environment, state that explicitly in the PR. Do not claim a check passed when it was not executed.

## Scope discipline

Implement only the active task specification in `docs/tasks/`.

Do not opportunistically add:

- Selenium;
- Playwright;
- browser automation;
- CAPTCHA bypass;
- anti-bot bypass;
- proxy pools;
- retries/backoff;
- queues/workers;
- distributed execution;
- persistence/database integration;
- service discovery;
- scraping logic for real competitors;

unless the current task explicitly requires it.

## Git / PR workflow

- Branch from the current `main`.
- Keep changes scoped to one task.
- Add/update automated tests with implementation changes.
- Do not merge your own PR unless explicitly instructed.
- PR description must list architecture decisions, security considerations, tests/checks actually executed, and any manual verification still required.
