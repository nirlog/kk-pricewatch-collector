# kk-pricewatch-collector

Standalone Python collection service for the [`nirlog/kk.pricewatch`](https://github.com/nirlog/kk.pricewatch)
Bitrix module. The HTTP collector protocol `1.0` is the only integration boundary; this
service does not import Bitrix code or access its database/filesystem.

Version **0.1.0** implements a deterministic protocol-compatible stub. It performs no
real scraping, browser automation, or outbound HTTP requests.

## Requirements and local setup

- Python 3.12+

```bash
python -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[dev]'
export KK_PRICEWATCH_API_TOKEN='local-test-token'
uvicorn app.main:create_app --factory --host 0.0.0.0 --port 8000
```

Settings use the `KK_PRICEWATCH_` environment prefix. `KK_PRICEWATCH_API_TOKEN` is
required and must be non-empty. The application does not automatically load `.env`;
export variables explicitly or use your process/container secret mechanism. The token
belongs only in the `Authorization: Bearer ...` header—never in URLs or JSON.

## Stub protocol

All examples are sent to `POST /api/collectors/browser` with `Content-Type:
application/json` and an Authorization bearer token.

Default success:

```json
{
  "schema_version": "1.0",
  "request_id": "e2e-1",
  "items": [{"id": "12", "url": "https://competitor.example/p/1?region=spb"}],
  "options": {
    "stub": {
      "default": {"type": "success", "price": "12345.67", "currency": "RUB"}
    }
  }
}
```

An item error or a mixed batch uses exact item-ID overrides:

```json
{
  "schema_version": "1.0",
  "request_id": "e2e-2",
  "items": [
    {"id": "12", "url": "https://competitor.example/p/1"},
    {"id": "13", "url": "https://competitor.example/p/2"}
  ],
  "options": {
    "stub": {
      "default": {"type": "success", "price": "12345.67", "currency": "RUB"},
      "results": {
        "13": {
          "type": "error",
          "code": "PRICE_NOT_FOUND",
          "message": "Stub price was not found"
        }
      }
    }
  }
}
```

Global protocol error simulation (returned with HTTP 200):

```json
{
  "schema_version": "1.0",
  "request_id": "e2e-3",
  "items": [{"id": "12", "url": "https://competitor.example/p/1"}],
  "options": {
    "stub": {
      "global_error": {"code": "COLLECTOR_ERROR", "message": "Stub global failure"}
    }
  }
}
```

Missing or malformed stub configuration produces the safe protocol error
`STUB_CONFIGURATION_ERROR`, also with HTTP 200.

## Quality checks

```bash
python -m pytest
ruff check .
ruff format --check .
mypy app
```

## Docker

The image uses Python 3.12, installs runtime dependencies only, and runs as a non-root
user. Supply the secret only at runtime:

```bash
docker build -t kk-pricewatch-collector:0.1.0 .
docker run --rm -p 8000:8000 \
  -e KK_PRICEWATCH_API_TOKEN='local-test-token' \
  kk-pricewatch-collector:0.1.0
```

## Bitrix E2E smoke test

With `kk.pricewatch >= 0.17.0`, configure the external collector base URL as
`http://127.0.0.1:8000`, use the same token, and set `COLLECTOR_HANDLER` to
`/api/collectors/browser`. Put one of the stub objects above in `COLLECTOR_OPTIONS`.
Confirm a successful price reaches `PriceUpdateService` and monitoring/history, then
test an item error and recovery to success. No Bitrix-side protocol changes are needed.
