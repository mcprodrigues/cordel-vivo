# ADR 0005: Authenticate the API with API keys, by Bearer or HTTP Basic

- **Status:** accepted
- **Date:** 2026-11-25
- **Issue:** #6

## Context

AGENTS.md requires authentication on every route, including `/docs` and `/openapi.json`; only `/health` is public (principle 10). FastAPI serves `/docs` and `/openapi.json` without authentication by default.

The callers in v1 are scripts, the future front end and the project owner opening `/docs` in a browser. No document asks for user accounts, roles or token expiry. A browser cannot attach an `Authorization: Bearer` header to a page it navigates to, but it does prompt for HTTP Basic credentials when the server sends that challenge.

## Decision

- Every request carries an API key, either as `Authorization: Bearer <key>` or as HTTP Basic with any user name and the key as password.
- Keys come from `CORDEL_API_KEYS`, separated by commas, so a new key can be added before the old one is removed. The application refuses to start without at least one non-blank key.
- Keys are held as `SecretStr` and compared with `secrets.compare_digest` against every configured key, without stopping at the first match.
- Authentication is a dependency of the whole FastAPI application, not of individual routers. A route added later is protected unless its path is added to an explicit public list, which today holds only `/health`.
- The default docs routes are disabled and served again by the application, so they go through the same dependency.
- A failed check returns `401` with `WWW-Authenticate: Basic realm="Cordel Vivo", Bearer`, which makes browsers show their login prompt.

## Consequences

- Protection is the default. Making a route public is a visible change to one list, which a test checks.
- There is no notion of users or permissions: every valid key can do everything. That is enough while only the project owner and her own clients call the API.
- Keys travel in every request, so any deployment outside the local machine must use HTTPS.
- Basic credentials are cached by the browser for the session, which is convenient for `/docs` but means "logging out" requires closing the browser.
- If the API gets external users, per-user permissions or expiring sessions, we revisit this and move to OAuth2 or JWT.

## Alternatives

- **Bearer only.** Simpler, but `/docs` would need a browser extension or a manual token field to open at all.
- **JWT with OAuth2 password flow.** Gives users and expiry, but needs user storage and token issuing that nothing in the plan requires.
- **A separate header such as `X-API-Key`.** Common, but browsers never prompt for it, and it adds a second scheme next to the standard `Authorization` header.
- **A reverse proxy in front of the API doing authentication.** Keeps the app simpler, but tests could no longer prove that every route is protected, and local runs would need the proxy too.
