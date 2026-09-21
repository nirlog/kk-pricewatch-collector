from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings

TOKEN = "unit-test-token"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(Settings(api_token=TOKEN))) as test_client:
        yield test_client


@pytest.fixture
def auth_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def minimal_payload() -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "request_id": "request-1",
        "items": [{"id": "12", "url": "https://example.test/p?b=2&a=1%20x"}],
        "options": {
            "stub": {"default": {"type": "success", "price": "12345.67", "currency": "RUB"}}
        },
    }
