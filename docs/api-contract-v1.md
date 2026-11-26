# Cordel Vivo API contract, v1

This file is the public contract of the API (`app/`). It changes in the same PR as the code (AGENTS.md, "Git workflow"), and it lists only what is implemented. The planned routes are in `docs/plano.md` ("Busca e API").

## Authentication

Every route except `/health` requires an API key, including `/docs` and `/openapi.json` (ADR 0005).

| Method | Header |
|---|---|
| Bearer, for programs | `Authorization: Bearer <key>` |
| HTTP Basic, for browsers | `Authorization: Basic base64(<any user>:<key>)`, so the browser login prompt opens `/docs` |

Keys are configured in `CORDEL_API_KEYS`, separated by commas. Several keys can be active at once, which allows rotation. The API refuses to start without at least one key.

A missing or invalid key returns:

```http
HTTP/1.1 401 Unauthorized
WWW-Authenticate: Basic realm="Cordel Vivo", Bearer
Content-Type: application/json

{"detail": "Missing or invalid API key"}
```

## Routes

### `GET /health`

Public. Liveness only: it says the process is up and does not check the database or storage.

```http
HTTP/1.1 200 OK
Content-Type: application/json

{"status": "ok"}
```

### `GET /docs`

Authenticated. Swagger UI for this API. The page loads the Swagger UI assets from a public CDN in the browser.

### `GET /openapi.json`

Authenticated. The OpenAPI schema. The schema documents the application routes. `/docs` and `/openapi.json` themselves are not listed in it.

## Running

```bash
CORDEL_API_KEYS=... CORDEL_API_HOST=127.0.0.1 CORDEL_API_PORT=8010 uv run python -m app
```

## Changelog

- 2026-11-25: first version, `/health` and authentication (#6).
