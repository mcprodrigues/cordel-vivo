"""Authentication rules (AGENTS.md, principle 10): only /health is public."""

import base64

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr, ValidationError

from app.main import create_app
from app.security import is_valid_key
from app.settings import Settings

KEY = "test-key-1"
OTHER_KEY = "test-key-2"


def settings(*keys: str) -> Settings:
    return Settings(api_keys=tuple(SecretStr(key) for key in keys))


def basic(password: str, user: str = "anyone") -> dict[str, str]:
    token = base64.b64encode(f"{user}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}


def bearer(key: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {key}"}


@pytest.fixture
def app() -> FastAPI:
    return create_app(settings(KEY, OTHER_KEY))


@pytest.fixture
def client(app: FastAPI) -> TestClient:
    return TestClient(app)


def test_health_is_public(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
def test_docs_and_openapi_require_auth(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 401
    assert response.headers["WWW-Authenticate"].startswith("Basic ")


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
def test_bearer_key_is_accepted(client: TestClient, path: str) -> None:
    assert client.get(path, headers=bearer(KEY)).status_code == 200


@pytest.mark.parametrize("path", ["/docs", "/openapi.json"])
def test_basic_with_key_as_password_is_accepted(client: TestClient, path: str) -> None:
    assert client.get(path, headers=basic(KEY)).status_code == 200


def test_every_configured_key_is_accepted(client: TestClient) -> None:
    for key in (KEY, OTHER_KEY):
        assert client.get("/openapi.json", headers=bearer(key)).status_code == 200


@pytest.mark.parametrize(
    "headers",
    [
        bearer("wrong-key"),
        bearer(""),
        basic("wrong-key"),
        basic(""),
        {"Authorization": "Basic not-base64!"},
        {"Authorization": f"Token {KEY}"},
        {"Authorization": KEY},
        {"X-API-Key": KEY},
    ],
    ids=[
        "wrong-bearer",
        "empty-bearer",
        "wrong-basic",
        "empty-basic",
        "malformed-basic",
        "unknown-scheme",
        "no-scheme",
        "other-header",
    ],
)
def test_invalid_credentials_are_rejected(client: TestClient, headers: dict[str, str]) -> None:
    assert client.get("/openapi.json", headers=headers).status_code == 401


def test_key_is_not_accepted_as_basic_user_name(client: TestClient) -> None:
    assert client.get("/openapi.json", headers=basic("wrong", user=KEY)).status_code == 401


def test_new_route_is_protected_by_default(app: FastAPI) -> None:
    @app.get("/v1/anything")
    def anything() -> dict[str, str]:
        return {"secret": "data"}

    client = TestClient(app)

    assert client.get("/v1/anything").status_code == 401
    assert client.get("/v1/anything", headers=bearer(KEY)).status_code == 200


def test_health_is_the_only_documented_public_route(client: TestClient) -> None:
    paths = client.get("/openapi.json", headers=bearer(KEY)).json()["paths"]

    assert set(paths) == {"/health"}


def test_api_refuses_to_start_without_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CORDEL_API_KEYS", raising=False)

    with pytest.raises(ValidationError):
        create_app()


@pytest.mark.parametrize("value", ["", " , ", ","])
def test_api_refuses_to_start_with_only_blank_keys(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv("CORDEL_API_KEYS", value)

    with pytest.raises(ValidationError):
        create_app()


def test_keys_are_read_from_comma_separated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CORDEL_API_KEYS", f" {KEY} ,{OTHER_KEY}")

    client = TestClient(create_app())

    assert client.get("/openapi.json", headers=bearer(KEY)).status_code == 200
    assert client.get("/openapi.json", headers=bearer(OTHER_KEY)).status_code == 200


def test_keys_are_not_exposed_in_settings_repr() -> None:
    assert KEY not in repr(settings(KEY))


def test_key_comparison_checks_whole_key() -> None:
    keys = (SecretStr(KEY),)

    assert is_valid_key(KEY, keys)
    assert not is_valid_key(KEY[:-1], keys)
    assert not is_valid_key(KEY + "x", keys)
