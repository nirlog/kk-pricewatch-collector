# Task 001 — Python Collector foundation + protocol-compatible stub

## Status

Planned

## Target version

`0.1.0`

## Context

`kk-pricewatch-collector` is a standalone Python service used by the 1C-Bitrix module `nirlog/kk.pricewatch` through the External Collector API.

The PHP side already defines collector protocol `1.0` and sends requests to a configured handler path such as:

```text
POST /api/collectors/browser
Authorization: Bearer <token>
Content-Type: application/json
Accept: application/json
```

Task 001 does **not** implement real website scraping. Its purpose is to establish the Python service foundation and a deterministic protocol-compatible stub so we can perform the first real E2E integration:

```text
kk.pricewatch (Bitrix)
    -> HTTP ExternalCollector
    -> kk-pricewatch-collector
    -> protocol 1.0 response
    -> PriceUpdateService
    -> monitoring/history
```

The service must remain independent from Bitrix internals and databases.

---

## 1. Goals

Implement a production-shaped service skeleton with:

- Python 3.12+;
- FastAPI;
- Pydantic v2;
- environment-based configuration;
- Bearer-token authentication;
- strict collector protocol `1.0` request/response models;
- one protocol endpoint: `/api/collectors/browser`;
- deterministic stub behavior controlled only by protocol `options`;
- Docker image;
- CI;
- tests that require no external network;
- basic documentation sufficient to run the first Bitrix -> Python E2E smoke test.

The architecture must allow Task 002+ to replace the stub acquisition behavior with real HTTP/browser collectors without changing protocol `1.0`.

---

## 2. Repository bootstrap

Create at minimum:

```text
kk-pricewatch-collector/
├── AGENTS.md
├── README.md
├── pyproject.toml
├── .gitignore
├── .env.example
├── Dockerfile
├── .dockerignore
├── .github/
│   └── workflows/
│       └── ci.yml
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── settings.py
│   ├── api/
│   │   ├── __init__.py
│   │   └── collectors.py
│   ├── contract/
│   │   ├── __init__.py
│   │   └── v1.py
│   ├── handlers/
│   │   ├── __init__.py
│   │   └── stub.py
│   └── security/
│       ├── __init__.py
│       └── bearer.py
├── tests/
│   ├── conftest.py
│   ├── test_auth.py
│   ├── test_contract_v1.py
│   └── test_stub_endpoint.py
└── docs/
    └── tasks/
        └── 001-protocol-compatible-stub.md
```

Exact file split may vary if there is a clear architectural reason, but keep HTTP, contract validation, authentication, and stub behavior separated.

Do not introduce a database.

---

## 3. Python/package configuration

Use `pyproject.toml` as the project metadata and tool configuration source.

Baseline dependencies:

- `fastapi`;
- `pydantic>=2`;
- `pydantic-settings`;
- `uvicorn`.

Development/test dependencies:

- `pytest`;
- `httpx` for FastAPI/TestClient-compatible HTTP tests;
- `ruff`;
- `mypy`.

Do not use Poetry unless there is a concrete reason. Prefer standard PEP 621 metadata and ordinary Python tooling.

Project version for Task 001:

```text
0.1.0
```

---

## 4. Application factory

Prefer an application factory so tests can inject settings without mutating global process state.

Example shape:

```python
create_app(settings: Settings | None = None) -> FastAPI
```

The production/runtime path loads settings from environment when explicit settings are not supplied.

Avoid requiring a real secret merely to import contract or handler modules.

Recommended Uvicorn launch shape:

```bash
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

---

## 5. Settings

Environment variable prefix:

```text
KK_PRICEWATCH_
```

Minimum setting:

```text
KK_PRICEWATCH_API_TOKEN
```

The configured API token must be a non-empty string for the runtime app.

Optional runtime settings may include host/port/log level only if useful, but do not create configuration surface without need.

`.env.example` must contain placeholders only, for example:

```dotenv
KK_PRICEWATCH_API_TOKEN=change-me
```

Do not commit a real token.

Do not automatically load arbitrary local `.env` secrets in CI unless explicitly controlled by settings tooling. Document expected behavior.

---

## 6. Authentication

Protect:

```text
POST /api/collectors/browser
```

with:

```text
Authorization: Bearer <token>
```

Requirements:

- missing Authorization header -> HTTP `401`;
- wrong auth scheme -> HTTP `401`;
- empty token -> HTTP `401`;
- wrong token -> HTTP `401`;
- correct token -> request continues;
- return `WWW-Authenticate: Bearer` on authentication failure;
- use constant-time token comparison, e.g. `hmac.compare_digest()`;
- never include configured token or supplied bad token in response body/log text;
- never log the Authorization header.

Authentication failure is an HTTP boundary failure and does not use collector protocol global-error JSON.

---

## 7. Collector request contract 1.0

Accepted JSON body:

```json
{
  "schema_version": "1.0",
  "request_id": "6e51b8a2-opaque-id",
  "items": [
    {
      "id": "12",
      "url": "https://competitor.example/product/1"
    },
    {
      "id": "13",
      "url": "https://competitor.example/product/2?region=spb"
    }
  ],
  "options": {}
}
```

Validation requirements:

- top level must be JSON object;
- `schema_version` exactly `"1.0"`;
- `request_id` non-empty string after trim check;
- `items` must be JSON list;
- at least one item required;
- each item must be JSON object;
- item `id` non-empty string after trim check;
- duplicate item IDs rejected;
- item `url` non-empty string after trim check;
- URL must otherwise be preserved exactly as received; protocol layer must not normalize query order, encoding, trailing slash, etc.;
- `options` must be JSON object/map;
- `options: []` is invalid;
- `options: {}` is valid;
- do not add Bitrix-specific fields to the model.

For Task 001 use strict models (`extra="forbid"`) for protocol request objects so accidental contract drift is detected early.

Malformed request/authentication errors may use normal FastAPI HTTP `4xx` responses. They are outside collector response semantics because the PHP client should only send valid protocol requests.

---

## 8. Collector response contract 1.0

### Global success

```json
{
  "schema_version": "1.0",
  "request_id": "6e51b8a2-opaque-id",
  "success": true,
  "items": [
    {
      "id": "12",
      "success": true,
      "price": "129990.00",
      "currency": "RUB"
    }
  ]
}
```

### Item failure

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

### Global protocol failure

```json
{
  "schema_version": "1.0",
  "request_id": "6e51b8a2-opaque-id",
  "success": false,
  "items": [],
  "error": {
    "code": "COLLECTOR_ERROR",
    "message": "Collector failed"
  }
}
```

Requirements:

- `request_id` is returned byte-for-byte/string-for-string unchanged;
- global success has no global `error`;
- global failure has `items: []` and a valid global `error`;
- item success has `price` and `currency`, and no item `error`;
- item failure has `error`, and no `price`/`currency`;
- response item IDs correspond exactly to requested item IDs;
- response item order should match request order for predictability, although PHP correlation must not depend on order.

Protocol-level global failure returned by the stub uses HTTP `200` with valid collector JSON.

---

## 9. Money / currency validation

Match the existing PHP contract exactly.

Price regex:

```text
^[0-9]+(?:\.[0-9]+)?$
```

Examples accepted:

```text
0
0.00
1
12345.67
```

Examples rejected:

```text
-1
+1
1,20
1 000
NaN
Infinity
```

Never use a binary float as protocol money representation.

Currency regex:

```text
^[A-Z]{3}$
```

Examples:

```text
RUB
USD
EUR
```

---

## 10. Error validation

Error code regex:

```text
^[A-Z0-9_]{1,64}$
```

Error message:

- string;
- non-empty after trim check;
- max length `4096` characters.

The service must never put the API token into any error message.

---

## 11. Deterministic stub behavior

Implement a dedicated `StubCollector`/stub handler. It must perform **no outbound HTTP requests**.

The stub is controlled by `request.options.stub`.

Supported configuration:

```json
{
  "stub": {
    "default": {
      "type": "success",
      "price": "12345.67",
      "currency": "RUB"
    },
    "results": {
      "13": {
        "type": "error",
        "code": "PRICE_NOT_FOUND",
        "message": "Stub price was not found"
      }
    }
  }
}
```

Semantics:

1. For each requested item, look for an exact `results[item.id]` override.
2. If no per-item override exists, use `default`.
3. Preserve request item order in response.
4. Do not inspect or fetch the item URL.
5. Do not mutate item IDs or URLs.

Supported result shapes:

Success:

```json
{
  "type": "success",
  "price": "12345.67",
  "currency": "RUB"
}
```

Error:

```json
{
  "type": "error",
  "code": "PRICE_NOT_FOUND",
  "message": "Stub price was not found"
}
```

All result values must pass the same response validation as normal protocol output.

### Global failure simulation

Also support:

```json
{
  "stub": {
    "global_error": {
      "code": "COLLECTOR_ERROR",
      "message": "Stub global failure"
    }
  }
}
```

If `global_error` is present and valid:

- return protocol global failure;
- `items` must be `[]`;
- HTTP status remains `200`;
- ignore `default/results` for that request.

### Missing/invalid stub configuration

`options` itself follows protocol `1.0` and can contain opaque future keys, but Task 001 stub-specific configuration must be validated explicitly.

If `/api/collectors/browser` receives no usable `options.stub.default`, no matching per-item result, and no `global_error`, return a protocol-level global failure:

```text
code: STUB_CONFIGURATION_ERROR
message: Stub collector configuration is missing or invalid.
```

Do not raise an unhandled exception.

For a malformed stub-specific structure that passes top-level protocol validation, prefer the same controlled protocol global failure rather than FastAPI 500.

---

## 12. Separation of concerns

Keep at least these logical boundaries:

```text
HTTP/FastAPI route
    -> authentication
    -> protocol request model
    -> stub handler/collector
    -> protocol response model
```

Do not put all logic into one FastAPI route.

The stub collector/handler should be callable in ordinary unit tests without an HTTP server.

The protocol models must not import FastAPI.

---

## 13. Exception handling

Expected stub/configuration errors must not produce stack traces to the client.

Unexpected internal exceptions at the handler boundary should become a safe protocol global failure where `request_id` is already known:

```text
COLLECTOR_ERROR
Collector failed.
```

Do not return raw Python exception messages to the Bitrix client.

Do not expose environment variables, filesystem paths, dependency versions, or secrets in protocol errors.

---

## 14. Logging

Keep logging minimal in Task 001.

Allowed useful context:

- request ID;
- endpoint/handler name;
- number of items;
- success/global failure status;
- duration if implemented safely.

Never log:

- Authorization header;
- bearer token;
- full request headers;
- environment dump;
- secrets.

Avoid logging full request/response bodies by default.

If request URLs are logged at all, make that an explicit later decision; Task 001 does not need URL logging.

---

## 15. Dockerfile

Provide a minimal production-oriented Dockerfile.

Requirements:

- Python 3.12 base;
- no browser packages in Task 001;
- install only runtime dependencies in final image where practical;
- run as non-root user;
- expose/listen on port `8000` by default;
- use Uvicorn application factory;
- do not bake API token into image;
- reasonable deterministic build behavior.

Do not add Playwright/Selenium/Chromium yet.

---

## 16. CI

Add GitHub Actions CI for pushes/PRs.

Minimum steps:

```bash
python -m pytest
ruff check .
ruff format --check .
mypy app
```

Use Python 3.12.

CI tests must not call the public internet or require real credentials.

Provide a test token only as local test configuration/environment inside CI, not as a repository secret.

---

## 17. Automated tests

Add comprehensive deterministic tests.

### Authentication

- valid Bearer token accepted;
- missing Authorization -> 401;
- wrong scheme -> 401;
- wrong token -> 401;
- bad token is not echoed;
- configured token is not echoed;
- `WWW-Authenticate: Bearer` is present on failure.

### Request contract

- valid minimal request;
- valid multiple items;
- wrong schema version;
- missing/empty request ID;
- `items` object instead of list;
- empty items list;
- item array/list instead of object;
- empty item ID;
- duplicate item IDs;
- empty URL;
- `options: {}` accepted;
- `options: []` rejected;
- unexpected top-level/item fields rejected.

### Stub behavior

- default success for one item;
- default success for multiple items;
- item-specific override;
- mixed success/error batch;
- exact item IDs preserved;
- request order preserved;
- full URLs/query strings accepted without fetching;
- valid global error -> HTTP 200 protocol failure;
- missing stub configuration -> controlled `STUB_CONFIGURATION_ERROR`;
- malformed stub result -> controlled global failure;
- invalid price rejected safely;
- invalid currency rejected safely;
- invalid error code rejected safely;
- empty/too-long error message rejected safely.

### Protocol output

- response `schema_version` exactly `1.0`;
- request ID round-trip;
- money stays JSON string;
- global success/failure field conflicts are impossible through typed models;
- item success/failure field conflicts are impossible through typed models.

### Network isolation

- stub unit/integration tests must not make outbound network calls.

---

## 18. README

Document:

- project purpose;
- relationship to `nirlog/kk.pricewatch`;
- Python version;
- install for local development;
- test/lint/type-check commands;
- environment variable `KK_PRICEWATCH_API_TOKEN`;
- Uvicorn launch command;
- Docker build/run example;
- `/api/collectors/browser` request example;
- stub `options` examples for success, item error, mixed batch, global error;
- security note that token belongs only in Authorization header;
- explicit note that Task 001 performs no real scraping/browser automation.

Do not include real credentials.

---

## 19. Manual E2E smoke after PR implementation

After Task 001 code is complete, but before considering the integration finished, manually validate with a test Bitrix installation running `kk.pricewatch >= 0.17.0`.

Example configuration:

```text
External Collector enabled: yes
Base URL: http://127.0.0.1:8000
Token: <same test token as Python service>
Connect timeout: 5
Request timeout: 60
```

Competitor:

```text
COLLECTOR_TYPE = external
COLLECTOR_HANDLER = /api/collectors/browser
```

Example `COLLECTOR_OPTIONS`:

```json
{
  "stub": {
    "default": {
      "type": "success",
      "price": "12345.67",
      "currency": "RUB"
    }
  }
}
```

Expected E2E:

1. Bitrix performs normal collection through `ExternalCollector`.
2. Python service authenticates request.
3. Stub returns protocol `1.0` success.
4. `kk.pricewatch` stores `12345.67 RUB` through existing `PriceUpdateService`.
5. Monitoring/history behaves exactly as for another successful collector.
6. Change stub default to an item error and confirm controlled error persistence.
7. Return to success and confirm recovery path.

No special Bitrix-side code may be added solely for this smoke test.

---

## 20. Acceptance criteria

Task 001 is complete only when all are true:

- repository has a working Python 3.12 FastAPI foundation;
- version is `0.1.0`;
- application is created through a testable factory;
- `/api/collectors/browser` exists;
- Bearer authentication works and uses constant-time comparison;
- secrets are not echoed/logged by application code;
- protocol request `1.0` is strictly validated;
- `options` is represented as JSON object/map;
- protocol response `1.0` matches the PHP contract;
- money/error validation matches contract rules;
- deterministic stub supports success, per-item error, mixed batch, and global error;
- stub performs no outbound HTTP requests;
- request IDs and item IDs round-trip correctly;
- Dockerfile runs service as non-root;
- CI exists and is green;
- pytest, Ruff, format check, and mypy pass;
- README explains local/Docker/E2E usage;
- no Selenium/Playwright/browser implementation is present;
- first Bitrix -> Python protocol smoke can be executed without changing contract `1.0`.

---

## 21. Out of scope

Do not implement in Task 001:

- real competitor HTTP scraping;
- HTML/XPath/CSS price extraction;
- JavaScript rendering;
- Playwright;
- Selenium;
- Chromium/browser dependencies;
- CAPTCHA handling;
- anti-bot bypass;
- proxy support;
- retries/backoff;
- async job queues;
- Celery/RQ;
- Redis;
- database/persistence;
- scheduled jobs;
- concurrency scaling;
- per-competitor secrets;
- health/service-discovery protocol;
- metrics/Prometheus;
- tracing infrastructure;
- automatic repricing;
- collector protocol `2.0`.

The next task should build on this foundation without breaking protocol `1.0`.

Suggested next milestone:

```text
Task 002 — Real HTTP collector foundation
```
